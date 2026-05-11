from datetime import datetime, timezone

from supabase import create_client, Client

from apps.api.config import get_settings

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


def ensure_user_exists(user_id: str) -> None:
    """Upsert auth user into public.users so FK constraints don't fail."""
    client = get_supabase()
    try:
        resp = client.auth.admin.get_user_by_id(user_id)
        email = resp.user.email if resp.user else None
    except Exception:
        email = None
    if not email:
        return
    client.table("users").upsert(
        {"id": user_id, "email": email},
        on_conflict="id",
    ).execute()


def get_user_email(user_id: str) -> str | None:
    """Return email for user_id from Supabase Auth. None on any error."""
    try:
        resp = get_supabase().auth.admin.get_user_by_id(user_id)
        return resp.user.email if resp.user else None
    except Exception:
        return None


def create_session(
    user_id: str,
    scenario_id: str,
    domain: str,
    difficulty: int,
    max_turns: int,
) -> dict:
    result = (
        get_supabase()
        .table("coaching_sessions")
        .insert(
            {
                "user_id": user_id,
                "scenario_id": scenario_id,
                "domain": domain,
                "difficulty": difficulty,
                "max_turns": max_turns,
            }
        )
        .execute()
    )
    return result.data[0]


def get_session(session_id: str) -> dict | None:
    result = (
        get_supabase()
        .table("coaching_sessions")
        .select("*")
        .eq("id", session_id)
        .execute()
    )
    if result.data:
        return result.data[0]
    return None


def insert_turn(
    session_id: str,
    turn_number: int,
    user_text: str,
    persona_reply: str,
    critic_json: dict,
    intent_class: str,
) -> None:
    get_supabase().table("coaching_turns").insert(
        {
            "session_id": session_id,
            "turn_number": turn_number,
            "user_text": user_text,
            "persona_reply": persona_reply,
            "critic_json": critic_json,
            "intent_class": intent_class,
        }
    ).execute()


def increment_turn_count(session_id: str) -> int:
    session = get_session(session_id)
    new_count = (session["turn_count"] or 0) + 1
    get_supabase().table("coaching_sessions").update(
        {"turn_count": new_count}
    ).eq("id", session_id).execute()
    return new_count


def end_session(
    session_id: str,
    summary: str,
    summary_embedding: list[float] | None,
    avg_score: float,
) -> None:
    update_data: dict = {
        "summary": summary,
        "avg_score": avg_score,
        "completed": True,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    if summary_embedding is not None:
        update_data["summary_embedding"] = summary_embedding
    get_supabase().table("coaching_sessions").update(
        update_data
    ).eq("id", session_id).execute()


def get_session_turns(session_id: str) -> list[dict]:
    result = (
        get_supabase()
        .table("coaching_turns")
        .select("*")
        .eq("session_id", session_id)
        .order("turn_number")
        .execute()
    )
    return result.data or []


def get_active_session(user_id: str, scenario_id: str) -> dict | None:
    result = (
        get_supabase()
        .table("coaching_sessions")
        .select("*")
        .eq("user_id", user_id)
        .eq("scenario_id", scenario_id)
        .eq("completed", False)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    session = result.data[0]
    if (session.get("turn_count") or 0) >= session.get("max_turns", 0):
        return None
    return session


def abandon_active_sessions(user_id: str, scenario_id: str) -> None:
    get_supabase().table("coaching_sessions").update(
        {
            "completed": True,
            "summary": "Session abandoned.",
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("user_id", user_id).eq("scenario_id", scenario_id).eq(
        "completed", False
    ).execute()


# ---------------------------------------------------------------------------
# L2 — alert_events
# ---------------------------------------------------------------------------

def insert_alert_event(
    alert_id: str,
    user_id: str,
    severity: str,
    risk_score: float,
    cause_tags: list,
    shap_values: dict,
    features: dict,
    rule_id: str,
    headline: str,
    person_msg: str,
    caregiver_msg: str,
    recommended_actions: list,
    why_narrative: str | None,
    demo: bool,
    cooldown_until: str | None,
) -> dict:
    result = (
        get_supabase()
        .table("alert_events")
        .insert(
            {
                "id": alert_id,
                "user_id": user_id,
                "severity": severity,
                "risk_score": risk_score,
                "cause_tags": cause_tags,
                "shap_values": shap_values,
                "features": features,
                "rule_id": rule_id,
                "headline": headline,
                "person_msg": person_msg,
                "caregiver_msg": caregiver_msg,
                "recommended_actions": recommended_actions,
                "why_narrative": why_narrative,
                "demo": demo,
                "cooldown_until": cooldown_until,
            }
        )
        .execute()
    )
    return result.data[0]


def get_alert_events(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    severity: str | None = None,
) -> list[dict]:
    q = (
        get_supabase()
        .table("alert_events")
        .select("*")
        .eq("user_id", user_id)
        .order("ts", desc=True)
        .limit(limit)
        .offset(offset)
    )
    if severity:
        q = q.eq("severity", severity)
    result = q.execute()
    return result.data or []


def get_alert_detail(alert_id: str) -> dict | None:
    result = (
        get_supabase()
        .table("alert_events")
        .select("*")
        .eq("id", alert_id)
        .execute()
    )
    if result.data:
        return result.data[0]
    return None


def acknowledge_alert(alert_id: str, acknowledged_by: str) -> None:
    get_supabase().table("alert_events").update(
        {
            "acknowledged": True,
            "acknowledged_by": acknowledged_by,
        }
    ).eq("id", alert_id).execute()


def mark_false_alarm(alert_id: str) -> None:
    get_supabase().table("alert_events").update(
        {"false_alarm": True}
    ).eq("id", alert_id).execute()


def insert_false_alarm(
    alert_id: str,
    user_id: str,
    reported_by: str,
    risk_score_at_alert: float,
    cause_tags_at_alert: list,
    shap_values_at_alert: dict,
    all_features_at_alert: dict,
    rule_id_fired: str,
    notes: str | None,
) -> None:
    get_supabase().table("alert_false_alarms").insert(
        {
            "alert_id": alert_id,
            "user_id": user_id,
            "reported_by": reported_by,
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "risk_score_at_alert": risk_score_at_alert,
            "cause_tags_at_alert": cause_tags_at_alert,
            "shap_values_at_alert": shap_values_at_alert,
            "all_features_at_alert": all_features_at_alert,
            "rule_id_fired": rule_id_fired,
            "notes": notes,
        }
    ).execute()


# ---------------------------------------------------------------------------
# L2 — user_profiles_extended
# ---------------------------------------------------------------------------

def get_user_profile_extended(user_id: str) -> dict | None:
    result = (
        get_supabase()
        .table("user_profiles_extended")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if result.data:
        return result.data[0]
    return None


def upsert_user_profile_extended(user_id: str, **fields) -> dict:
    result = (
        get_supabase()
        .table("user_profiles_extended")
        .upsert({"user_id": user_id, **fields}, on_conflict="user_id")
        .execute()
    )
    return result.data[0]


# ---------------------------------------------------------------------------
# L3 — memory retrieval (unchanged)
# ---------------------------------------------------------------------------

def retrieve_past_summaries(
    user_id: str,
    query_embedding: list[float],
    domain: str,
    threshold: float = 0.40,
    top_k: int = 3,
) -> list[dict]:
    result = (
        get_supabase()
        .rpc(
            "match_past_sessions",
            {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_domain": domain,
                "match_threshold": threshold,
                "match_count": top_k,
            },
        )
        .execute()
    )
    return result.data or []
