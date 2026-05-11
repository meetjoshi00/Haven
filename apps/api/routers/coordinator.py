"""L2 Coordinator — L1→L2 bridge.

Responsibilities:
  1. Load YAML rules + calibration thresholds at startup.
  2. Receive L1 payload (POST /coordinator/ingest).
  3. Check per-user cooldown (in-memory; demo mode skips).
  4. Match rules (all evaluated; highest severity wins).
  5. Build alert payload (Phase 1: static narrative; Phase 2: Groq + Redis).
  6. Persist alert_event to DB.
  7. Set cooldown.
  8. Return AlertPayload (or None if no rule fires / in cooldown).

Phase 2 will extend ingest() to add:
  - Groq narrative generation + Upstash Redis cache
  - Supabase Realtime broadcast
  - Resend email to person + emergency contact
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.chains.narrative import (
    FALLBACK_NARRATIVE,
    build_narrative_chain,
    trim_to_25_words,
)
from apps.api.routers.alerts import (
    AlertPayload,
    AppAction,
    L1Payload,
    build_alert_payload,
    persist_alert,
)
from apps.api.services.notifications import broadcast_realtime, send_email
from apps.api.services.redis_cache import get_cached_narrative, set_cached_narrative
from apps.api import db as _db

logger = logging.getLogger(__name__)
router = APIRouter()

_ROOT = Path(__file__).parent.parent.parent.parent
_RULES_PATH = _ROOT / "rules" / "intervention_rules.yaml"
_CAL_FULL_PATH = _ROOT / "ml" / "models" / "risk_calibration.json"
_CAL_WEARABLE_PATH = _ROOT / "ml" / "models" / "risk_calibration_wearable.json"

_rules: list[dict] = []
_cooldowns: dict[str, datetime] = {}  # user_id → cooldown_until (UTC)

_SEVERITY_ORDER: dict[str, int] = {"high": 2, "medium": 1, "low": 0}


# ---------------------------------------------------------------------------
# Startup — rule loading
# ---------------------------------------------------------------------------

def load_rules() -> None:
    """Load rules from YAML. Called once from FastAPI lifespan."""
    global _rules
    if not _RULES_PATH.exists():
        logger.warning("intervention_rules.yaml not found at %s", _RULES_PATH)
        _rules = []
        return

    with _RULES_PATH.open() as f:
        data = yaml.safe_load(f)

    _rules = data.get("rules", [])
    logger.info("L2 rules loaded: %d rules", len(_rules))

    for rule in _rules:
        logger.debug("  rule: %s  severity=%s", rule["id"], rule["severity"])


# ---------------------------------------------------------------------------
# Cooldown helpers
# ---------------------------------------------------------------------------

def _is_in_cooldown(user_id: str, demo: bool) -> bool:
    if demo:
        return False
    until = _cooldowns.get(user_id)
    if until is None:
        return False
    return datetime.now(timezone.utc) < until


def _set_cooldown(user_id: str, cooldown_minutes: int, demo: bool) -> str | None:
    if demo or cooldown_minutes == 0:
        return None
    until = datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)
    _cooldowns[user_id] = until
    return until.isoformat()


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------

def _rule_matches(rule: dict, payload: L1Payload) -> bool:
    cond = rule.get("condition", {})

    # Model-type-specific risk_score threshold
    if payload.model_type == "full":
        threshold = float(cond.get("risk_score_gte_full", 0.0))
    else:
        threshold = float(cond.get("risk_score_gte_wearable", 0.0))

    if payload.risk_score < threshold:
        return False

    # cause_tags_any: OR — any listed tag must be present in payload
    required_tags = cond.get("cause_tags_any", [])
    if required_tags:
        if not any(tag in payload.cause_tags for tag in required_tags):
            return False

    # demo flag: if condition specifies demo, payload must match exactly
    if "demo" in cond:
        if cond["demo"] != payload.demo:
            return False

    return True


def match_rule(payload: L1Payload) -> dict | None:
    """Evaluate all rules, return highest-severity match (file order breaks ties)."""
    matches = [r for r in _rules if _rule_matches(r, payload)]
    if not matches:
        return None
    return max(matches, key=lambda r: _SEVERITY_ORDER.get(r["severity"], 0))


# ---------------------------------------------------------------------------
# Phase 2 helpers — narrative + notifications
# ---------------------------------------------------------------------------

async def get_narrative(cause_tags: list[str]) -> str:
    """cache → Groq → static fallback. Never raises."""
    try:
        cached = await get_cached_narrative(cause_tags)
        if cached:
            logger.debug("Narrative cache hit tags=%s", cause_tags)
            return cached
    except Exception as exc:
        logger.warning("Cache GET error: %s", exc)
    try:
        chain = build_narrative_chain()
        tags_str = ", ".join(cause_tags) if cause_tags else "general stress"
        raw = await chain.ainvoke({"cause_tags": tags_str})
        narrative = trim_to_25_words(raw.strip())
        if narrative:
            try:
                await set_cached_narrative(cause_tags, narrative)
            except Exception as exc:
                logger.warning("Cache SET error: %s", exc)
            return narrative
    except Exception as exc:
        logger.warning("Groq narrative failed: %s", exc)
    return FALLBACK_NARRATIVE


async def dispatch_notifications(alert: AlertPayload, payload: L1Payload) -> None:
    """Realtime always. Email only in non-demo mode. Never raises."""
    tasks = [
        broadcast_realtime(f"user:{alert.user_id}", "alert", alert.model_dump())
    ]
    if not payload.demo:
        user_email = _db.get_user_email(alert.user_id)
        if user_email:
            tasks.append(send_email(
                user_email,
                alert.headline,
                f"<p>{alert.person_message}</p><p><em>{alert.why}</em></p>",
            ))
        profile = _db.get_user_profile_extended(alert.user_id)
        ec_email = (profile or {}).get("emergency_contact_email")
        if ec_email:
            tasks.append(send_email(
                ec_email,
                alert.headline,
                f"<p>{alert.caregiver_message}</p>",
            ))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning("Notification task %d failed: %s", i, r)


# ---------------------------------------------------------------------------
# Core ingest pipeline
# ---------------------------------------------------------------------------

async def ingest(payload: L1Payload) -> AlertPayload | None:
    """Main L1→L2 pipeline. Returns None if no rule fires or cooldown active."""
    if not _rules:
        logger.warning("No L2 rules loaded — skipping ingest")
        return None

    if _is_in_cooldown(payload.user_id, payload.demo):
        logger.debug("Cooldown active for user %s — skipping", payload.user_id)
        return None

    matched = match_rule(payload)
    if matched is None:
        logger.debug(
            "No rule matched: risk=%.4f cause_tags=%s demo=%s model=%s",
            payload.risk_score, payload.cause_tags, payload.demo, payload.model_type,
        )
        return None

    logger.info(
        "Rule fired: %s  severity=%s  risk=%.4f  user=%s  demo=%s",
        matched["id"], matched["severity"], payload.risk_score,
        payload.user_id, payload.demo,
    )

    alert_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    cooldown_until = _set_cooldown(
        payload.user_id, matched.get("cooldown_minutes", 0), payload.demo
    )

    why = await get_narrative(payload.cause_tags)

    alert = build_alert_payload(
        rule=matched,
        payload=payload,
        why=why,
        alert_id=alert_id,
        cooldown_until=cooldown_until,
        ts=ts,
    )

    try:
        persist_alert(alert, payload.shap_values, payload.features)
    except Exception as exc:
        logger.error("Failed to persist alert %s: %s", alert_id, exc)

    await dispatch_notifications(alert, payload)

    return alert


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=AlertPayload | None)
async def coordinator_ingest(payload: L1Payload) -> AlertPayload | None:
    """Accepts an L1 tick payload. Returns alert if a rule fired, else null.

    Frontend calls this once per SSE tick (every 5s during demo).
    In production, the sensor bridge calls this directly.
    """
    return await ingest(payload)


@router.get("/rules")
async def list_rules():
    """Debug endpoint — returns loaded rules summary (no sensitive data)."""
    return [
        {
            "id": r["id"],
            "severity": r["severity"],
            "headline": r.get("headline"),
            "cooldown_minutes": r.get("cooldown_minutes"),
        }
        for r in _rules
    ]


# ---------------------------------------------------------------------------
# User profile endpoints (L2)
# ---------------------------------------------------------------------------

class UserProfileUpdateRequest(BaseModel):
    phone_number: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_email: str | None = None
    notify_emergency_on: str | None = None
    notify_self_on: str | None = None
    alert_sensitivity: str | None = None


@router.get("/profile/{user_id}")
async def get_profile(user_id: str):
    """Return user_profiles_extended row for user_id, or 404 if not found."""
    profile = _db.get_user_profile_extended(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profile/{user_id}")
async def update_profile(user_id: str, body: UserProfileUpdateRequest):
    """Upsert user_profiles_extended for user_id. Returns updated row."""
    _db.ensure_user_exists(user_id)
    fields = body.model_dump(exclude_unset=True)
    return _db.upsert_user_profile_extended(user_id, **fields)
