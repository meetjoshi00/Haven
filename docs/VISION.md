# Vision

## The why

Autistic individuals face a double challenge: social interaction is genuinely harder to navigate, and the feedback loop for learning is slow, inconsistent, and often delivered in ways that don't work for them. Existing social skills training is largely clinic-based, expensive, and unavailable at the moment of need.

This system addresses three distinct points of failure:
- **Before escalation** — detect physiological stress before it becomes a crisis (Layer 1)
- **At escalation** — notify the person themselves and their support network with actionable, real-time guidance (Layer 2)
- **Between episodes** — give autistic individuals a safe, low-stakes space to practise social scenarios at their own pace (Layer 3)

The goal is not to make autistic individuals behave more neurotypically. It is to give them tools to navigate a world that wasn't designed for them, on their own terms.

---

## Primary users

### Autistic individual (Layer 2 + Layer 3 user)
- Teen or adult (13+), any support needs level
- Uses the coaching chatbot independently, at own pace (L3)
- Receives gentle, self-directed alerts when their own stress escalates (L2)
- Needs: low sensory load, literal language, no ambiguity in UI, no pressure
- Fears: being judged, being wrong, unexpected changes in flow
- Success: feels more confident in real social situations; can self-regulate earlier with system support

### Caregiver / emergency contact (Layer 2 user)
- Parent, support worker, teacher, clinician, or any trusted person registered by the individual
- Receives real-time alerts when the person they support may need attention
- Not always physically present — system notifies via SMS and email, not only in-app
- Needs: clear, actionable guidance — not jargon, not vague warnings
- Fears: missing a signal, overreacting, being blamed for not acting
- Success: catches escalation early, responds appropriately, false alarm rate stays low

### Clinician / researcher (future user)
- Reviews session history, rubric scores, escalation patterns over time
- Not in scope for current build — placeholder only

---

## Clinical grounding

**What this system is not:**
- A diagnostic tool
- A replacement for therapy
- A system that pathologises autistic behaviour
- A tool that trains masking

**What the rubrics measure:**
Contextual communication effectiveness — did the user's response serve their goal in the scenario? Feedback is framed as skill-building, not correction toward neurotypical norms (Milton 2012 double empathy principle).

**Scenario difficulty design:**
Based on PEERS curriculum (Laugeson & Frankel 2011) — difficulty reflects the social complexity of the situation, not the "correctness" of any particular communication style.

**Layer 1 signal labelling:**
All user-facing labels say "stress escalation risk" — never "meltdown prediction." The model predicts precursors, not events. Overclaiming certainty causes caregiver over-intervention. The person themselves never sees their raw risk score — only a gentle, actionable message.

**Layer 2 false alarm design:**
Both the person and their caregiver can mark an alert as a false alarm. Full physiological parameters at the time of the alert are stored with every false alarm report. This data drives threshold recalibration over time, reducing alert fatigue without sacrificing sensitivity.

---

## Success metrics (clinical)

| Metric | Target |
|---|---|
| Layer 3 rubric score improvement across sessions | Positive trend over 5+ sessions |
| Layer 1 AUROC | ≥ 0.80 (Imbiriba et al. 2024 benchmark) |
| Layer 2 false alarm rate | < 20% of alerts marked false alarm |
| Layer 2 self-alert acknowledgement rate | > 60% of person-facing alerts acknowledged (not dismissed) |
| Distress safe-response activation | Never results in session continuation — always clears |
