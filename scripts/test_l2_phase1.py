"""L2 Phase 1 — test suite.

Two sections:
  SECTION A — Unit tests (no server, no DB required)
    Rule matching, cooldown logic, payload building.
    Run standalone: python scripts/test_l2_phase1.py

  SECTION B — Integration tests (API server must be running)
    POST /coordinator/ingest, GET /alerts, acknowledge, false alarm.
    Requires: uvicorn running + Supabase DB migration applied.
    Run: python scripts/test_l2_phase1.py --integration

Usage:
  python scripts/test_l2_phase1.py                  # unit tests only
  python scripts/test_l2_phase1.py --integration     # unit + integration
"""
import sys
import time
from pathlib import Path

# Windows CP1252 consoles can't print box-drawing chars — force UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml

# ── Helpers ──────────────────────────────────────────────────────────────────

PASS_COUNT = 0
FAIL_COUNT = 0


def ok(desc: str) -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  PASS  {desc}")


def fail(desc: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    msg = f"  FAIL  {desc}"
    if detail:
        msg += f"\n        {detail}"
    print(msg)


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── SECTION A — Unit tests ────────────────────────────────────────────────────

section("A1 — YAML rule file loads correctly")

rules_path = ROOT / "rules" / "intervention_rules.yaml"
if not rules_path.exists():
    fail("YAML exists", f"Not found: {rules_path}")
else:
    with rules_path.open() as f:
        raw = yaml.safe_load(f)
    rules = raw.get("rules", [])

    if len(rules) >= 6:
        ok(f"Rule count: {len(rules)} (>=6)")
    else:
        fail(f"Rule count", f"Expected >=6, got {len(rules)}")

    required_ids = {
        "full_escalation_urgent",
        "motor_agitation_elevated",
        "internal_arousal_sustained",
        "physiological_stress_elevated",
        "demo_mode",
    }
    found_ids = {r["id"] for r in rules}
    missing = required_ids - found_ids
    if not missing:
        ok("All required rule IDs present")
    else:
        fail("Required rule IDs", f"Missing: {missing}")

    last = rules[-1]
    if last["id"] == "demo_mode":
        ok("demo_mode is last rule (catch-all ordering correct)")
    else:
        fail("demo_mode ordering", f"Last rule is '{last['id']}', expected 'demo_mode'")

    urgent = next((r for r in rules if r["id"] == "full_escalation_urgent"), None)
    if urgent and urgent["severity"] == "high":
        ok("full_escalation_urgent severity=high")
    else:
        fail("full_escalation_urgent severity", f"Got {urgent}")

    if urgent:
        gte_full = urgent["condition"].get("risk_score_gte_full", 0)
        gte_wear = urgent["condition"].get("risk_score_gte_wearable", 0)
        if gte_full > 0.90:
            ok(f"full_escalation_urgent full threshold={gte_full:.4f} (>0.90)")
        else:
            fail("full_escalation_urgent full threshold", f"Got {gte_full}")
        if gte_wear > 0.80:
            ok(f"full_escalation_urgent wearable threshold={gte_wear:.4f} (>0.80)")
        else:
            fail("full_escalation_urgent wearable threshold", f"Got {gte_wear}")

section("A2 — Rule matching logic")

import apps.api.routers.coordinator as coord
from apps.api.routers.alerts import L1Payload, build_alert_payload, FALLBACK_NARRATIVE

coord._rules = rules

_cases = [
    # (risk, tags, model, demo, expected_rule_id, description)
    (0.20, [],                    "full",     False, None,                          "below full q25 → no match"),
    (0.30, ["motor_agitation"],   "full",     False, None,                          "motor_agitation but risk 0.30 < 0.3435 → no match"),
    (0.45, ["motor_agitation"],   "full",     False, "motor_agitation_elevated",    "motor_agitation + risk 0.45 full → medium"),
    (0.45, ["escalating_arousal"],"full",     False, "internal_arousal_sustained",  "escalating_arousal → arousal rule"),
    (0.45, ["sustained_stress"],  "full",     False, "internal_arousal_sustained",  "sustained_stress → arousal rule (OR match)"),
    (0.45, ["physiological_stress"],"full",   False, "physiological_stress_elevated","physiological_stress → stress rule"),
    (0.45, ["above_personal_baseline"],"full",False, "physiological_stress_elevated","above_personal_baseline → stress rule"),
    (0.45, ["fatigue_accumulation"],"full",   False, "fatigue_accumulation",        "fatigue_accumulation → fatigue rule"),
    (0.97, ["motor_agitation"],   "full",     False, "full_escalation_urgent",      "risk 0.97 → high severity wins"),
    (0.97, [],                    "full",     False, "full_escalation_urgent",      "risk 0.97 no tags → urgent (no tag filter)"),
    (0.45, [],                    "full",     True,  "demo_mode",                   "demo=True no tags → demo_mode"),
    (0.45, ["motor_agitation"],   "full",     True,  "motor_agitation_elevated",    "demo + motor_agitation → physiological rule wins"),
    (0.35, ["motor_agitation"],   "wearable", False, None,                          "wearable 0.35 < q25=0.3615 → no match"),
    (0.37, ["motor_agitation"],   "wearable", False, "motor_agitation_elevated",    "wearable 0.37 > q25=0.3615 → match"),
    (0.90, ["motor_agitation"],   "wearable", False, "full_escalation_urgent",      "wearable 0.90 > q90=0.8835 → urgent"),
    (0.88, ["motor_agitation"],   "wearable", False, "motor_agitation_elevated",    "wearable 0.88 < q90=0.8835 → medium"),
]

for risk, tags, model, demo, expected, desc in _cases:
    p = L1Payload(
        risk_score=risk, cause_tags=tags, ts="2026-05-06T12:00:00Z",
        user_id="00000000-0000-0000-0000-000000000001",
        model_type=model, demo=demo,
    )
    matched = coord.match_rule(p)
    got = matched["id"] if matched else None
    if got == expected:
        ok(desc)
    else:
        fail(desc, f"Expected '{expected}', got '{got}'")

section("A3 — Cooldown logic")

import uuid
from datetime import datetime, timedelta, timezone

coord._cooldowns.clear()

uid = str(uuid.uuid4())

# Not in cooldown → False
assert not coord._is_in_cooldown(uid, demo=False)
ok("Fresh user → not in cooldown")

# Set 10-minute cooldown
ret = coord._set_cooldown(uid, cooldown_minutes=10, demo=False)
assert ret is not None
ok(f"set_cooldown(10m) returns ISO timestamp: {ret[:19]}")

# Now in cooldown
assert coord._is_in_cooldown(uid, demo=False)
ok("User now in cooldown")

# Demo always bypasses
assert not coord._is_in_cooldown(uid, demo=True)
ok("Demo=True bypasses cooldown")

# demo_mode rule → set_cooldown(0) returns None
ret2 = coord._set_cooldown(uid + "_demo", cooldown_minutes=0, demo=True)
assert ret2 is None
ok("cooldown_minutes=0 returns None (no cooldown set)")

# Different user → not affected
uid2 = str(uuid.uuid4())
assert not coord._is_in_cooldown(uid2, demo=False)
ok("Different user_id unaffected by another's cooldown")

coord._cooldowns.clear()

section("A4 — AlertPayload construction")

import uuid as _uuid

test_rule = next(r for r in rules if r["id"] == "motor_agitation_elevated")
test_payload = L1Payload(
    risk_score=0.52,
    cause_tags=["motor_agitation"],
    shap_values={"acc_svm_mean": 0.18},
    features={"acc_svm_mean": 82.0, "gsr_phasic_peak_count": 5.0},
    ts="2026-05-06T12:00:00Z",
    user_id="00000000-0000-0000-0000-000000000001",
    model_type="full",
    demo=True,
)
aid = str(_uuid.uuid4())
alert = build_alert_payload(
    rule=test_rule,
    payload=test_payload,
    why=FALLBACK_NARRATIVE,
    alert_id=aid,
    cooldown_until=None,
    ts="2026-05-06T12:00:00Z",
)

assert alert.alert_id == aid,             "alert_id"
assert alert.severity == "medium",        "severity"
assert alert.risk_score == 0.52,          "risk_score stored"
assert alert.cause_tags == ["motor_agitation"], "cause_tags"
assert alert.why == FALLBACK_NARRATIVE,   "why fallback"
assert alert.demo is True,               "demo flag"
assert len(alert.app_actions) == 2,       "app_actions"
assert alert.app_actions[0].action == "false_alarm",  "first action"
assert alert.app_actions[1].action == "acknowledge",  "second action"
ok("AlertPayload fields correct")

# Person never sees risk_score — verify field is present but would be filtered in UI
assert hasattr(alert, "risk_score")
ok("risk_score field present (UI responsibility to hide from person)")

# Rule id recorded
assert alert.rule_id == "motor_agitation_elevated"
ok("rule_id stored on payload")

# ── SECTION B — Integration tests ────────────────────────────────────────────

RUN_INTEGRATION = "--integration" in sys.argv

if not RUN_INTEGRATION:
    print(f"\n{'─' * 60}")
    print("  SECTION B — Integration tests SKIPPED")
    print("  Run with --integration flag (requires server + DB)")
    print(f"{'─' * 60}")
else:
    import httpx

    API = "http://localhost:8000"
    TEST_USER = "00000000-0000-0000-0000-000000000001"

    section("B1 — Server health")

    try:
        resp = httpx.get(f"{API}/health", timeout=5)
        if resp.status_code == 200:
            ok("GET /health 200")
        else:
            fail("GET /health", f"status={resp.status_code}")
    except Exception as e:
        fail("Server unreachable", str(e))
        print("\n  Cannot run integration tests — start the API first:")
        print("    .venv\\Scripts\\activate")
        print("    uvicorn apps.api.main:app --reload --port 8000")
        print()
        sys.exit(1)

    section("B2 — Rules endpoint")

    resp = httpx.get(f"{API}/coordinator/rules")
    if resp.status_code == 200:
        loaded = resp.json()
        ok(f"GET /coordinator/rules 200 — {len(loaded)} rules")
    else:
        fail("GET /coordinator/rules", resp.text)

    section("B3 — Coordinator ingest: below threshold → null")

    payload_below = {
        "risk_score": 0.20, "cause_tags": [], "shap_values": {},
        "features": {}, "ts": "2026-05-06T12:00:00Z",
        "user_id": TEST_USER, "model_type": "full", "demo": True,
    }
    resp = httpx.post(f"{API}/coordinator/ingest", json=payload_below, timeout=10)
    if resp.status_code == 200 and resp.json() is None:
        ok("risk=0.20 → null (no rule fires)")
    else:
        fail("below threshold", f"status={resp.status_code} body={resp.text[:200]}")

    section("B4 — Coordinator ingest: escalating demo → alert created")

    payload_esc = {
        "risk_score": 0.55,
        "cause_tags": ["motor_agitation", "escalating_arousal"],
        "shap_values": {"acc_svm_mean": 0.19, "gsr_tonic_slope": 0.14},
        "features": {"acc_svm_mean": 82.0, "gsr_tonic_slope": 0.04, "gsr_phasic_peak_count": 7.5},
        "ts": "2026-05-06T12:00:00Z",
        "user_id": TEST_USER,
        "model_type": "full",
        "demo": True,
    }
    resp = httpx.post(f"{API}/coordinator/ingest", json=payload_esc, timeout=10)
    if resp.status_code != 200:
        fail("ingest escalating", f"status={resp.status_code} body={resp.text[:300]}")
        alert_id = None
    else:
        alert = resp.json()
        if alert is None:
            fail("ingest escalating", "Got null — cooldown may be active from previous run; restart server to clear")
            alert_id = None
        else:
            alert_id = alert.get("alert_id")
            ok(f"Alert created: {alert_id}")

            sev = alert.get("severity")
            if sev == "medium":
                ok(f"severity=medium (motor_agitation_elevated beats demo_mode, same severity → file order)")
            else:
                fail("severity", f"Expected medium, got {sev}")

            rule = alert.get("rule_id")
            if rule == "motor_agitation_elevated":
                ok(f"rule_id=motor_agitation_elevated")
            else:
                fail("rule_id", f"Got {rule}")

            if alert.get("demo") is True:
                ok("demo=True on alert")
            else:
                fail("demo flag", f"Got {alert.get('demo')}")

            if alert.get("cooldown_until") is None:
                ok("cooldown_until=None (demo mode)")
            else:
                fail("cooldown_until", f"Expected None, got {alert.get('cooldown_until')}")

            # Risk score must NOT appear in person_message
            pm = alert.get("person_message", "")
            if "0.55" not in pm and "0." not in pm:
                ok("person_message contains no raw score")
            else:
                fail("person_message", f"Contains score-like text: {pm[:100]}")

    section("B5 — GET /alerts/{user_id}")

    resp = httpx.get(f"{API}/alerts/{TEST_USER}", timeout=10)
    if resp.status_code == 200:
        items = resp.json()
        ok(f"GET /alerts/{TEST_USER} 200 — {len(items)} alert(s)")
        if items:
            item = items[0]
            required_keys = {"alert_id", "severity", "headline", "cause_tags", "acknowledged", "false_alarm", "demo", "ts"}
            missing = required_keys - set(item.keys())
            if not missing:
                ok("AlertListItem has all required fields")
            else:
                fail("AlertListItem fields", f"Missing: {missing}")
    else:
        fail(f"GET /alerts/{TEST_USER}", resp.text[:200])

    section("B6 — GET /alerts/{alert_id}/detail")

    if alert_id:
        resp = httpx.get(f"{API}/alerts/{alert_id}/detail", timeout=10)
        if resp.status_code == 200:
            detail = resp.json()
            ok("GET /alerts/{id}/detail 200")
            if "features" in detail and isinstance(detail["features"], dict):
                ok(f"features JSONB present ({len(detail['features'])} keys)")
            else:
                fail("features in detail", str(detail.get("features")))
            if "shap_values" in detail:
                ok("shap_values present in detail")
            else:
                fail("shap_values in detail", "missing")
        else:
            fail("GET /alerts/{id}/detail", resp.text[:200])
    else:
        print("  SKIP  (no alert_id from B4)")

    section("B7 — POST /alerts/{id}/acknowledge")

    if alert_id:
        resp = httpx.post(
            f"{API}/alerts/{alert_id}/acknowledge",
            json={"acknowledged_by": "caregiver"},
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            ok("acknowledge → {ok: true}")
        else:
            fail("acknowledge", resp.text[:200])

        # Verify persisted in DB via detail endpoint
        resp2 = httpx.get(f"{API}/alerts/{alert_id}/detail", timeout=10)
        if resp2.status_code == 200:
            d = resp2.json()
            if d.get("acknowledged") is True and d.get("acknowledged_by") == "caregiver":
                ok("acknowledged=True + acknowledged_by=caregiver persisted in DB")
            else:
                fail("acknowledged DB state", f"acknowledged={d.get('acknowledged')} by={d.get('acknowledged_by')}")
    else:
        print("  SKIP  (no alert_id from B4)")

    section("B8 — POST /alerts/{id}/false-alarm")

    # Create a fresh alert for false alarm test (no cooldown on demo)
    resp = httpx.post(f"{API}/coordinator/ingest", json=payload_esc, timeout=10)
    fa_alert_id = None
    if resp.status_code == 200 and resp.json():
        fa_alert_id = resp.json().get("alert_id")
        ok(f"Second alert created for false alarm test: {fa_alert_id}")
    else:
        print("  SKIP  second alert creation failed (cooldown or DB issue)")

    if fa_alert_id:
        resp = httpx.post(
            f"{API}/alerts/{fa_alert_id}/false-alarm",
            json={"reported_by": "user", "notes": "Felt fine — no stress"},
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            ok("false-alarm → {ok: true}")
        else:
            fail("false-alarm endpoint", resp.text[:200])

        # Verify false_alarm=True in DB
        resp2 = httpx.get(f"{API}/alerts/{fa_alert_id}/detail", timeout=10)
        if resp2.status_code == 200 and resp2.json().get("false_alarm") is True:
            ok("false_alarm=True persisted in DB")
        else:
            fail("false_alarm DB state", str(resp2.json().get("false_alarm") if resp2.status_code == 200 else resp2.text[:100]))

    section("B9 — High severity: full_escalation_urgent")

    payload_urgent = {
        "risk_score": 0.97,
        "cause_tags": ["motor_agitation", "escalating_arousal"],
        "shap_values": {"acc_svm_mean": 0.31, "gsr_tonic_slope": 0.22},
        "features": {"acc_svm_mean": 90.0, "gsr_tonic_slope": 0.09},
        "ts": "2026-05-06T12:00:00Z",
        "user_id": TEST_USER,
        "model_type": "full",
        "demo": True,
    }
    resp = httpx.post(f"{API}/coordinator/ingest", json=payload_urgent, timeout=10)
    if resp.status_code == 200 and resp.json():
        urgent_alert = resp.json()
        if urgent_alert.get("severity") == "high":
            ok("severity=high for risk=0.97")
        else:
            fail("high severity", f"Got {urgent_alert.get('severity')}")
        if urgent_alert.get("rule_id") == "full_escalation_urgent":
            ok("rule_id=full_escalation_urgent")
        else:
            fail("rule_id urgent", f"Got {urgent_alert.get('rule_id')}")
    else:
        fail("urgent ingest", f"status={resp.status_code} body={resp.text[:200]}")

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"\n{'═' * 60}")
total = PASS_COUNT + FAIL_COUNT
print(f"  {PASS_COUNT}/{total} passed  ({FAIL_COUNT} failed)")
print(f"{'═' * 60}")
sys.exit(0 if FAIL_COUNT == 0 else 1)
