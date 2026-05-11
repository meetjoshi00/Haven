from langchain_core.runnables import RunnableParallel

from apps.api.chains.intent import build_intent_chain, parse_intent
from apps.api.chains.persona import build_persona_chain
from apps.api.chains.critic import build_critic_chain
from apps.api.content import ContentStore
from apps.api.db import retrieve_past_summaries, get_session_turns
from apps.api.embeddings import embed_text, build_topic_text
from apps.api.config import MEMORY_COSINE_THRESHOLD, MEMORY_TOP_K


async def process_turn(
    session_id: str,
    user_text: str,
    content: ContentStore,
    session: dict,
) -> dict:
    scenario = content.scenarios[session["scenario_id"]]
    meta = scenario["metadata"]

    # Fetch prior turns early so intent classifier has conversation context
    prior_turns = get_session_turns(session_id)
    last_persona_message = (
        prior_turns[-1]["persona_reply"] if prior_turns else meta["opening_line"]
    )

    intent_chain = build_intent_chain()
    raw_intent = await intent_chain.ainvoke({
        "user_text": user_text,
        "scenario_title": meta["title"],
        "setting": meta["setting"],
        "last_persona_message": last_persona_message,
    })
    intent = parse_intent(raw_intent)

    if intent == "DISTRESS":
        return {
            "intent": "DISTRESS",
            "persona_reply": content.safe_response_text,
            "critic": None,
            "is_distress": True,
        }

    if intent == "OFF_TOPIC":
        persona_data = content.personas[meta["persona"]]
        persona_name = persona_data["metadata"]["name"]
        return {
            "intent": "OFF_TOPIC",
            "persona_reply": (
                f"I'm not sure about that! So, back to why you're here — "
                f"what would you like to say to {persona_name}?"
            ),
            "critic": None,
            "is_distress": False,
        }

    if intent == "SCENARIO_QUESTION":
        persona_data = content.personas[meta["persona"]]
        answer = (
            f"In this scenario, you're practising: "
            f"{', '.join(meta['skills_primary'])}. "
            f"{meta['setting'].strip()} "
            f"What would you like to say to {persona_data['metadata']['name']}?"
        )
        return {
            "intent": "SCENARIO_QUESTION",
            "persona_reply": answer,
            "critic": None,
            "is_distress": False,
        }

    # ROLEPLAY_TURN — full chain
    persona = content.personas[meta["persona"]]
    rubric = content.rubrics[meta["rubric"]]

    # Memory retrieval (non-fatal on failure)
    memory_context = ""
    try:
        topic_statement = (
            f"A practice session about {meta.get('title', '')} "
            f"focusing on {', '.join(meta.get('skills_primary', []))} "
            f"in the {meta.get('domain', '')} domain"
        )
        current_embedding = embed_text(topic_statement)
        past_sessions = retrieve_past_summaries(
            user_id=session["user_id"],
            query_embedding=current_embedding,
            domain=session["domain"],
            threshold=MEMORY_COSINE_THRESHOLD,
            top_k=MEMORY_TOP_K,
        )
        if past_sessions:
            memory_lines = [
                f"- {s['summary']} (score: {s['avg_score']})"
                for s in past_sessions
            ]
            memory_context = (
                "Previous session context:\n" + "\n".join(memory_lines)
            )
    except Exception:
        memory_context = ""

    # Build conversation history from already-fetched prior turns
    conversation_lines: list[str] = []
    if not prior_turns:
        conversation_lines.append(f"Persona: {meta['opening_line']}")
    else:
        conversation_lines.append(f"Persona: {meta['opening_line']}")
        for t in prior_turns:
            conversation_lines.append(f"User: {t['user_text']}")
            conversation_lines.append(f"Persona: {t['persona_reply']}")
    conversation_history = "\n".join(conversation_lines)

    # Parallel LLM calls
    persona_chain = build_persona_chain()
    critic_chain = build_critic_chain()

    good_examples = "\n".join(
        f"- {ex}" for ex in meta.get("good_turn_examples", [])
    )
    bad_examples = "\n".join(
        f"- {ex}" for ex in meta.get("bad_turn_examples", [])
    )

    previous_suggestion = ""
    if prior_turns and prior_turns[-1].get("critic_json"):
        previous_suggestion = prior_turns[-1]["critic_json"].get("suggestion", "")

    merged_input = {
        # persona prompt variables
        "persona_name": persona["metadata"]["name"],
        "persona_description": persona["metadata"]["description"],
        "patience_level": persona["metadata"]["patience_level"],
        "setting": meta["setting"],
        "memory_context": memory_context,
        "conversation_history": conversation_history,
        "user_text": user_text,
        # critic prompt variables
        "scenario_title": meta["title"],
        "rubric_text": rubric["body"],
        "good_examples": good_examples,
        "bad_examples": bad_examples,
        "previous_suggestion": previous_suggestion,
    }

    parallel = RunnableParallel(
        persona_reply=persona_chain,
        critic=critic_chain,
    )

    results = await parallel.ainvoke(merged_input)

    return {
        "intent": "ROLEPLAY_TURN",
        "persona_reply": results["persona_reply"],
        "critic": results["critic"],
        "is_distress": False,
    }
