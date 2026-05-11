import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.content import ContentStore
from apps.api.config import DEFAULT_MAX_TURNS, MIN_TURNS, MAX_TURNS_CAP
from apps.api.deps import get_content
from apps.api.safety import check_distress
from apps.api.db import (
    abandon_active_sessions,
    create_session,
    ensure_user_exists,
    get_active_session,
    get_session,
    insert_turn,
    increment_turn_count,
    end_session as db_end_session,
    get_session_turns,
)
from apps.api.chains.router import process_turn
from apps.api.chains.summary import build_summary_chain
from apps.api.embeddings import embed_text, build_topic_text

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────


class SessionStartRequest(BaseModel):
    user_id: str
    scenario_id: str


class SessionStartResponse(BaseModel):
    session_id: str
    opening_line: str
    scenario_title: str


class CriticSchema(BaseModel):
    score: Optional[int] = None
    suggestion: Optional[str] = None


class SessionTurnRequest(BaseModel):
    session_id: str
    user_text: str = Field(..., max_length=2000)


class SessionTurnResponse(BaseModel):
    intent: str
    persona_reply: str
    critic: Optional[CriticSchema] = None
    turn_number: int
    turns_remaining: int
    session_complete: bool


class SessionEndRequest(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    summary: str
    avg_score: float
    skills_practiced: list[str]


class ActiveSessionResponse(BaseModel):
    session_id: str
    turn_count: int
    max_turns: int
    started_at: str


class TurnData(BaseModel):
    turn_number: int
    user_text: str
    persona_reply: str
    critic_json: dict
    intent_class: Optional[str] = None


class SessionResumeResponse(BaseModel):
    session_id: str
    scenario_id: str
    scenario_title: str
    opening_line: str
    persona_name: str
    domain: str
    difficulty: int
    turn_count: int
    max_turns: int
    turns: list[TurnData]


class ScenarioListItem(BaseModel):
    id: str
    title: str
    domain: str
    difficulty: int
    skills_primary: list[str]
    estimated_turns: int
    reviewed: bool
    persona_name: str = ""
    setting: str = ""


# ── Internal helpers ──────────────────────────────────────────────


async def _end_session_internal(
    session_id: str,
    content: ContentStore,
    session: dict,
) -> dict:
    turns = get_session_turns(session_id)

    if not turns:
        db_end_session(session_id, "No turns recorded.", None, 0.0)
        return {"summary": "No turns recorded.", "avg_score": 0.0, "skills_practiced": []}

    scores = [
        t["critic_json"].get("score", 3)
        for t in turns
        if t.get("critic_json")
    ]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 3.0

    scenario = content.scenarios.get(session["scenario_id"], {})
    meta = scenario.get("metadata", {})
    skills = meta.get("skills_primary", [])

    # Close session immediately so it's never left as a zombie
    db_end_session(session_id, "Session completed.", None, avg_score)

    summary = "Session completed."
    try:
        conversation_log = "\n".join(
            f"Turn {t['turn_number']}: User said: {t['user_text']} "
            f"| Persona replied: {t['persona_reply']} "
            f"| Score: {t['critic_json'].get('score', '?') if t.get('critic_json') else '?'}"
            for t in turns
        )

        summary_chain = build_summary_chain()
        summary = await summary_chain.ainvoke(
            {
                "scenario_title": meta.get("title", "Unknown"),
                "domain": session.get("domain", ""),
                "skills": ", ".join(skills),
                "turn_count": str(len(turns)),
                "avg_score": f"{avg_score:.1f}",
                "conversation_log": conversation_log,
            }
        )

        summary_embedding = embed_text(f"{summary} | {build_topic_text(meta)}")
        db_end_session(session_id, summary, summary_embedding, avg_score)
    except Exception:
        logger.warning("Summary generation failed for session %s", session_id, exc_info=True)

    return {"summary": summary, "avg_score": avg_score, "skills_practiced": skills}


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/session/start", response_model=SessionStartResponse)
async def session_start(
    body: SessionStartRequest,
    content: ContentStore = Depends(get_content),
):
    if body.scenario_id not in content.scenarios:
        raise HTTPException(status_code=404, detail=f"Scenario {body.scenario_id} not found")

    ensure_user_exists(body.user_id)
    abandon_active_sessions(body.user_id, body.scenario_id)

    scenario = content.scenarios[body.scenario_id]
    meta = scenario["metadata"]

    max_turns = max(MIN_TURNS, min(MAX_TURNS_CAP, meta.get("estimated_turns", DEFAULT_MAX_TURNS)))

    session = create_session(
        user_id=body.user_id,
        scenario_id=body.scenario_id,
        domain=meta["domain"],
        difficulty=meta["difficulty"],
        max_turns=max_turns,
    )

    return SessionStartResponse(
        session_id=session["id"],
        opening_line=meta["opening_line"],
        scenario_title=meta["title"],
    )


@router.post("/session/turn", response_model=SessionTurnResponse)
async def session_turn(
    body: SessionTurnRequest,
    content: ContentStore = Depends(get_content),
):
    session = get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("completed"):
        raise HTTPException(status_code=400, detail="Session already completed")

    # DISTRESS CHECK — always first, safety-critical
    if check_distress(body.user_text, content.distress_keywords):
        return SessionTurnResponse(
            intent="DISTRESS",
            persona_reply=content.safe_response_text,
            critic=None,
            turn_number=session["turn_count"],
            turns_remaining=session["max_turns"] - session["turn_count"],
            session_complete=False,
        )

    result = await process_turn(
        session_id=body.session_id,
        user_text=body.user_text,
        content=content,
        session=session,
    )

    # Intent classifier also caught distress
    if result.get("is_distress"):
        return SessionTurnResponse(
            intent="DISTRESS",
            persona_reply=content.safe_response_text,
            critic=None,
            turn_number=session["turn_count"],
            turns_remaining=session["max_turns"] - session["turn_count"],
            session_complete=False,
        )

    # ROLEPLAY_TURN — persist turn, check completion
    if result["intent"] == "ROLEPLAY_TURN":
        new_turn_count = increment_turn_count(body.session_id)
        insert_turn(
            session_id=body.session_id,
            turn_number=new_turn_count,
            user_text=body.user_text,
            persona_reply=result["persona_reply"],
            critic_json=result["critic"],
            intent_class=result["intent"],
        )

        session_complete = new_turn_count >= session["max_turns"]

        if session_complete:
            await _end_session_internal(body.session_id, content, session)

        return SessionTurnResponse(
            intent=result["intent"],
            persona_reply=result["persona_reply"],
            critic=CriticSchema(**result["critic"]) if result.get("critic") else None,
            turn_number=new_turn_count,
            turns_remaining=max(0, session["max_turns"] - new_turn_count),
            session_complete=session_complete,
        )

    # OFF_TOPIC or SCENARIO_QUESTION — no persist, no turn increment
    return SessionTurnResponse(
        intent=result["intent"],
        persona_reply=result["persona_reply"],
        critic=None,
        turn_number=session["turn_count"],
        turns_remaining=session["max_turns"] - session["turn_count"],
        session_complete=False,
    )


@router.post("/session/end", response_model=SessionEndResponse)
async def session_end(
    body: SessionEndRequest,
    content: ContentStore = Depends(get_content),
):
    session = get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("completed"):
        scenario = content.scenarios.get(session["scenario_id"], {})
        skills = scenario.get("metadata", {}).get("skills_primary", [])
        return SessionEndResponse(
            summary=session.get("summary", ""),
            avg_score=session.get("avg_score", 0.0),
            skills_practiced=skills,
        )

    result = await _end_session_internal(body.session_id, content, session)
    return SessionEndResponse(**result)


@router.get("/session/active", response_model=ActiveSessionResponse)
async def get_active_session_endpoint(user_id: str, scenario_id: str):
    session = get_active_session(user_id, scenario_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active session")
    return ActiveSessionResponse(
        session_id=session["id"],
        turn_count=session["turn_count"] or 0,
        max_turns=session["max_turns"],
        started_at=str(session["started_at"]),
    )


@router.get("/session/{session_id}/resume", response_model=SessionResumeResponse)
async def resume_session_endpoint(
    session_id: str,
    content: ContentStore = Depends(get_content),
):
    session = get_session(session_id)
    if not session or session.get("completed"):
        raise HTTPException(status_code=404, detail="Session not found or already completed")
    turns = get_session_turns(session_id)
    scenario = content.scenarios.get(session["scenario_id"], {})
    meta = scenario.get("metadata", {})
    persona_data = content.personas.get(meta.get("persona", ""), {})
    persona_name = persona_data.get("metadata", {}).get("name", "")
    return SessionResumeResponse(
        session_id=session_id,
        scenario_id=session["scenario_id"],
        scenario_title=meta.get("title", ""),
        opening_line=meta.get("opening_line", ""),
        persona_name=persona_name,
        domain=session["domain"] or "",
        difficulty=session["difficulty"] or 1,
        turn_count=session["turn_count"] or 0,
        max_turns=session["max_turns"],
        turns=[TurnData(**t) for t in turns],
    )


@router.get("/scenarios", response_model=list[ScenarioListItem])
async def list_scenarios(
    domain: Optional[str] = None,
    difficulty: Optional[int] = None,
    tags: Optional[str] = None,
    content: ContentStore = Depends(get_content),
):
    results = []
    for sid, data in content.scenarios.items():
        meta = data["metadata"]
        if domain and meta.get("domain") != domain:
            continue
        if difficulty is not None and meta.get("difficulty") != difficulty:
            continue
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            scenario_tags = meta.get("tags", [])
            if not any(t in scenario_tags for t in tag_list):
                continue

        persona_id = meta.get("persona", "")
        persona_data = content.personas.get(persona_id, {})
        persona_name = persona_data.get("metadata", {}).get("name", "")

        results.append(
            ScenarioListItem(
                id=meta["id"],
                title=meta["title"],
                domain=meta["domain"],
                difficulty=meta["difficulty"],
                skills_primary=meta.get("skills_primary", []),
                estimated_turns=meta.get("estimated_turns", DEFAULT_MAX_TURNS),
                reviewed=meta.get("reviewed", False),
                persona_name=persona_name,
                setting=meta.get("setting", ""),
            )
        )

    return sorted(results, key=lambda x: (x.domain, x.difficulty, x.id))


@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    content: ContentStore = Depends(get_content),
):
    if scenario_id not in content.scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")

    meta = dict(content.scenarios[scenario_id]["metadata"])
    for field in ("good_turn_examples", "bad_turn_examples", "common_mistakes", "notes"):
        meta.pop(field, None)

    return meta
