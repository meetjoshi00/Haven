"""L2 alert CRUD endpoints.

Pydantic models used here are the shared contract between the coordinator
and all API consumers. coordinator.py imports AlertPayload from this module.

Endpoints:
  POST /alerts/trigger              — create alert (for testing; coordinator calls internally)
  POST /alerts/{id}/acknowledge
  POST /alerts/{id}/false-alarm
  GET  /alerts/{user_id}            — history, ?limit&offset&severity
  GET  /alerts/{alert_id}/detail    — full payload incl. features (caregiver-only)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api import db

logger = logging.getLogger(__name__)
router = APIRouter()

from apps.api.chains.narrative import FALLBACK_NARRATIVE  # noqa: F401 — re-export


# ---------------------------------------------------------------------------
# Pydantic models (shared with coordinator.py)
# ---------------------------------------------------------------------------

class AppAction(BaseModel):
    label: str
    action: Literal["false_alarm", "acknowledge"]


class AlertPayload(BaseModel):
    alert_id: str
    user_id: str
    severity: Literal["low", "medium", "high"]
    risk_score: float
    cause_tags: list[str]
    headline: str
    person_message: str
    caregiver_message: str
    why: str
    recommended_actions: list[str]
    app_actions: list[AppAction]
    cooldown_until: str | None
    rule_id: str
    demo: bool
    ts: str


class L1Payload(BaseModel):
    risk_score: float
    cause_tags: list[str]
    shap_values: dict[str, float] = {}
    features: dict[str, float] = {}
    ts: str
    user_id: str
    model_type: Literal["full", "wearable"] = "full"
    demo: bool = False


class AcknowledgeRequest(BaseModel):
    acknowledged_by: Literal["user", "caregiver"]


class FalseAlarmRequest(BaseModel):
    reported_by: Literal["user", "caregiver"]
    notes: str | None = None


class AlertListItem(BaseModel):
    alert_id: str
    severity: str
    headline: str
    cause_tags: list[str]
    acknowledged: bool
    false_alarm: bool
    demo: bool
    ts: str


class AlertDetail(AlertPayload):
    features: dict[str, float]
    shap_values: dict[str, float]
    acknowledged: bool
    acknowledged_by: str | None
    false_alarm: bool


# ---------------------------------------------------------------------------
# Internal helpers (called by coordinator without going through HTTP)
# ---------------------------------------------------------------------------

def build_alert_payload(
    rule: dict,
    payload: L1Payload,
    why: str,
    alert_id: str,
    cooldown_until: str | None,
    ts: str,
) -> AlertPayload:
    app_actions = [
        AppAction(label=a["label"], action=a["action"])
        for a in rule.get("app_actions", [])
    ]
    return AlertPayload(
        alert_id=alert_id,
        user_id=payload.user_id,
        severity=rule["severity"],
        risk_score=round(payload.risk_score, 4),
        cause_tags=payload.cause_tags,
        headline=rule["headline"],
        person_message=rule["person_message"],
        caregiver_message=rule["caregiver_message"],
        why=why,
        recommended_actions=rule.get("recommended_actions", []),
        app_actions=app_actions,
        cooldown_until=cooldown_until,
        rule_id=rule["id"],
        demo=payload.demo,
        ts=ts,
    )


def persist_alert(
    alert: AlertPayload,
    shap_values: dict,
    features: dict,
) -> None:
    db.ensure_user_exists(alert.user_id)
    db.insert_alert_event(
        alert_id=alert.alert_id,
        user_id=alert.user_id,
        severity=alert.severity,
        risk_score=alert.risk_score,
        cause_tags=alert.cause_tags,
        shap_values=shap_values,
        features=features,
        rule_id=alert.rule_id,
        headline=alert.headline,
        person_msg=alert.person_message,
        caregiver_msg=alert.caregiver_message,
        recommended_actions=alert.recommended_actions,
        why_narrative=alert.why,
        demo=alert.demo,
        cooldown_until=alert.cooldown_until,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{alert_id}/detail", response_model=AlertDetail)
async def get_alert_detail(alert_id: str):
    row = db.get_alert_detail(alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertDetail(
        alert_id=row["id"],
        user_id=row["user_id"],
        severity=row["severity"],
        risk_score=row["risk_score"],
        cause_tags=row["cause_tags"] or [],
        headline=row["headline"],
        person_message=row["person_msg"],
        caregiver_message=row["caregiver_msg"],
        why=row.get("why_narrative") or FALLBACK_NARRATIVE,
        recommended_actions=row.get("recommended_actions") or [],
        app_actions=[
            AppAction(label="I'm okay — false alarm", action="false_alarm"),
            AppAction(label="Noted, thank you", action="acknowledge"),
        ],
        cooldown_until=row.get("cooldown_until"),
        rule_id=row["rule_id"],
        demo=row.get("demo", False),
        ts=row["ts"],
        features=row.get("features") or {},
        shap_values=row.get("shap_values") or {},
        acknowledged=row.get("acknowledged", False),
        acknowledged_by=row.get("acknowledged_by"),
        false_alarm=row.get("false_alarm", False),
    )


@router.get("/{user_id}", response_model=list[AlertListItem])
async def get_alerts(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    severity: str | None = None,
):
    rows = db.get_alert_events(
        user_id=user_id, limit=limit, offset=offset, severity=severity
    )
    return [
        AlertListItem(
            alert_id=r["id"],
            severity=r["severity"],
            headline=r["headline"],
            cause_tags=r.get("cause_tags") or [],
            acknowledged=r.get("acknowledged", False),
            false_alarm=r.get("false_alarm", False),
            demo=r.get("demo", False),
            ts=r["ts"],
        )
        for r in rows
    ]


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert_endpoint(alert_id: str, body: AcknowledgeRequest):
    row = db.get_alert_detail(alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.acknowledge_alert(alert_id=alert_id, acknowledged_by=body.acknowledged_by)
    return {"ok": True}


@router.post("/{alert_id}/false-alarm")
async def report_false_alarm(alert_id: str, body: FalseAlarmRequest):
    row = db.get_alert_detail(alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.insert_false_alarm(
        alert_id=alert_id,
        user_id=row["user_id"],
        reported_by=body.reported_by,
        risk_score_at_alert=row["risk_score"],
        cause_tags_at_alert=row.get("cause_tags") or [],
        shap_values_at_alert=row.get("shap_values") or {},
        all_features_at_alert=row.get("features") or {},
        rule_id_fired=row["rule_id"],
        notes=body.notes,
    )
    db.mark_false_alarm(alert_id=alert_id)
    return {"ok": True}


@router.post("/trigger", response_model=AlertPayload | None)
async def trigger_alert(body: L1Payload):
    """HTTP convenience wrapper — calls the same logic as coordinator.ingest().

    Returns null if no rule matches or cooldown is active.
    Primary use: testing and future production sensor bridge.
    """
    from apps.api.routers.coordinator import ingest
    return await ingest(body)
