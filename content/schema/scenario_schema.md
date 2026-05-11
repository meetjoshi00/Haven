# Scenario Frontmatter Schema
## Locked field definitions for all 30 scenario files

Every scenario file in /content/scenarios/ must have frontmatter
matching this schema exactly. Never rename fields after indexing —
pgvector, LangChain retriever, and future LangGraph routing all
read these field names directly.

To add a new field: add it here first, update index_scenarios.py,
then add to scenario files. Never remove or rename existing fields.

---

## Full annotated schema

```yaml
---
# ── IDENTITY ─────────────────────────────────────────────────────
id: social_001
# Unique identifier. Never change after first indexing.
# Format: {domain}_{three-digit-number}
# Values: social_001–social_012, sensory_001–sensory_008,
#         workplace_001–workplace_010

title: "Ordering a coffee"
# Human-readable. Shown in UI scenario selection grid.
# Keep under 50 chars.

version: 1
# Increment by 1 whenever content changes.
# index_scenarios.py checks this against stored version —
# only re-embeds if version has changed. Saves compute.

# ── CLASSIFICATION ────────────────────────────────────────────────
domain: social
# social | sensory | workplace | school
# Drives pgvector metadata filter and UI domain filter.

subdomain: food_and_drink
# Finer-grain tag for future filtering. Not used in routing yet.
# Examples: food_and_drink, public_transport, education,
#           professional, peer_social, self_advocacy

difficulty: 1
# 1 = patient persona, forgiving reactions
# 2 = neutral persona, realistic reactions
# 3 = realistic persona, mildly impatient, some pushback
# Must match persona_patience field below.

age_language: universal
# universal       = plain clear English, works for all ages
# child_friendly  = simpler vocabulary, shorter sentences
# adult           = full professional/formal register allowed
# LangChain prompt assembly adjusts system prompt tone based on this.

estimated_turns: 12
# Expected turns to complete this scenario naturally.
# Default 12. Override here if scenario needs fewer (e.g. 8 for
# very simple diff-1 scenarios) or more (e.g. 14 for complex diff-3).
# Hard cap in system: 16. Minimum: 6.

# ── SKILLS ───────────────────────────────────────────────────────
skills_primary:
  - politeness
# 1–2 skills max. The main thing this scenario trains.
# Used in: pgvector embedding, session summary, UI card display,
#          session end "skills practiced" screen.
# Valid values: politeness, turn_taking, clarity_of_request,
#   self_advocacy, assertiveness, disagreement_handling,
#   tone_regulation, professional_register, active_listening,
#   conflict_resolution, emotional_regulation, humor_appropriate

skills_secondary:
  - turn_taking
  - clarity_of_request
# 0–3 skills. Supporting skills also practiced.
# Same valid values as skills_primary.

rubric: social_basic
# Which rubric file loads for the critic LLM call.
# social_basic             → /content/rubrics/social_basic.md
# social_advanced          → /content/rubrics/social_advanced.md
# sensory_advocacy         → /content/rubrics/sensory_advocacy.md
# workplace_communication  → /content/rubrics/workplace_communication.md
#
# Mapping by difficulty:
#   social domain,     diff 1-2 → social_basic
#   social domain,     diff 3   → social_advanced
#   sensory domain,    all      → sensory_advocacy
#   workplace/school,  all      → workplace_communication

# ── PERSONA ──────────────────────────────────────────────────────
persona: barista_rushed
# Which persona file loads for the roleplay LLM call.
# barista_rushed      → /content/personas/barista_rushed.md
# stranger_helpful    → /content/personas/stranger_helpful.md
# shop_assistant      → /content/personas/shop_assistant.md
# friend_casual       → /content/personas/friend_casual.md
# teacher_patient     → /content/personas/teacher_patient.md
# colleague_friendly  → /content/personas/colleague_friendly.md
# interviewer_formal  → /content/personas/interviewer_formal.md

persona_patience: high
# high   = patient, forgiving, re-asks gently if unclear (diff 1)
# medium = neutral, moves on if interaction stalls (diff 2)
# low    = mildly impatient, realistic workplace/social friction (diff 3)
# Must match difficulty:
#   difficulty 1 → persona_patience: high
#   difficulty 2 → persona_patience: medium
#   difficulty 3 → persona_patience: low

# ── CONTENT ──────────────────────────────────────────────────────
setting: >
  A busy coffee shop during the morning rush. The barista is
  friendly but moving quickly between orders. Other customers
  are waiting behind you.
# Injected into roleplay system prompt as scene context.
# 2–4 sentences. Sets stakes and atmosphere.
# Use > for multi-line YAML block scalar.

opening_line: "Next please! What can I get you?"
# The persona's first line — shown to user at session start.
# Must be in character and match persona's patience level.
# This is what the user responds to on Turn 1.

good_turn_examples:
  - "Could I please have a medium latte? No sugar, thank you."
  - "Hi, I'd like a black coffee please. Medium size."
  - "Excuse me, could I get an oat milk flat white? Thank you so much."
# 3–5 examples of turns that would score 4–5 on the rubric.
# Used in critic system prompt as positive exemplars.
# Not shown to user — server-side only.

bad_turn_examples:
  - "Coffee."
  - "I don't know, maybe a latte or something, I haven't decided."
  - "Why is it so loud in here? I just want a coffee."
# 3–5 examples of turns that would score 1–2 on the rubric.
# Used in critic system prompt as negative exemplars.
# Not shown to user — server-side only.

common_mistakes:
  - "Forgetting to say please or thank you"
  - "Not specifying size or milk type, causing unnecessary follow-up questions"
  - "Starting with a complaint or comment instead of the request"
# 2–4 most frequent errors for this scenario.
# Informs rubric loading and may be used in future hint system.
# Not shown to user directly.

# ── PEERS MAPPING ────────────────────────────────────────────────
peers_skills:
  - "Making requests of others"
  - "Using a polite tone of voice"
# Maps this scenario to specific PEERS curriculum skill names.
# Reference: Laugeson & Frankel (2010), Laugeson et al. (2014).
# Used for clinical reporting and academic defensibility.
# Not shown to user.

# ── PROGRESSION ──────────────────────────────────────────────────
prerequisite_scenarios: []
# List of scenario IDs that should be completed before this one.
# Empty = no prerequisite (scenario is immediately available).
# Currently metadata only. Will drive LangGraph routing in Phase 4.
# Example: [social_001, social_002]

unlocks_scenarios:
  - social_002
  - social_003
# Scenarios that become recommended after completing this one.
# Currently metadata only. Will drive LangGraph unlock logic in Phase 4.

recommended_next:
  - social_002
# The single best next scenario to suggest at session end.
# Shown on session summary screen as "Try next: [title]".
# Should be one step up in difficulty or a complementary skill.

# ── META ─────────────────────────────────────────────────────────
tags:
  - cafe
  - strangers
  - requesting
  - public_space
# Free-form tags for filtering and future semantic search.
# Used in pgvector embedding string alongside title + domain + skills.
# Keep to 3–6 tags per scenario.

reviewed: false
# false = generated content, not yet reviewed by autistic user or clinician
# true  = reviewed and approved
# Shown as badge on UI scenario card when true.
# Set to true only after participatory review — never auto-set.

notes: ""
# Internal notes for content authors. Never shown to user or injected
# into any prompt. Use for flagging ambiguity, review comments, etc.
---
```

---

## Complete example — social_001

```yaml
---
id: social_001
title: "Ordering a coffee"
version: 1
domain: social
subdomain: food_and_drink
difficulty: 1
age_language: universal
estimated_turns: 10
skills_primary:
  - politeness
skills_secondary:
  - turn_taking
  - clarity_of_request
rubric: social_basic
persona: barista_rushed
persona_patience: high
setting: >
  A busy coffee shop during the morning rush. The barista is
  friendly but moving quickly between orders. Other customers
  are waiting behind you.
opening_line: "Next please! What can I get you?"
good_turn_examples:
  - "Could I please have a medium latte? No sugar, thank you."
  - "Hi, I'd like a black coffee please. Medium size."
  - "Excuse me, could I get an oat milk flat white? Thank you so much."
bad_turn_examples:
  - "Coffee."
  - "I don't know, maybe a latte or something, I haven't decided."
  - "Why is it so loud in here? I just want a coffee."
common_mistakes:
  - "Forgetting to say please or thank you"
  - "Not specifying size or milk type, causing unnecessary follow-up questions"
  - "Starting with a complaint instead of the request"
peers_skills:
  - "Making requests of others"
  - "Using a polite tone of voice"
prerequisite_scenarios: []
unlocks_scenarios:
  - social_002
  - social_003
recommended_next: social_002
tags:
  - cafe
  - strangers
  - requesting
  - public_space
reviewed: false
notes: ""
---

## Setting

A busy coffee shop during the morning rush. The barista is friendly
but moving quickly between orders. Other customers are waiting behind you.

## What to practise

Making a clear, polite request to a stranger in a service context.
Focus on: including please/thank you, being specific about what you want,
keeping the interaction brief and efficient.

## The scenario

The barista greets you and waits for your order.
```

---

## Field reference — quick lookup

| Field | Type | Required | Drives |
|---|---|---|---|
| id | string | yes | pgvector key, API, all routing |
| title | string | yes | UI display |
| version | int | yes | re-embed trigger |
| domain | enum | yes | pgvector filter, UI filter |
| subdomain | string | yes | future filtering |
| difficulty | 1/2/3 | yes | persona selection, rubric selection |
| age_language | enum | yes | prompt assembly tone |
| estimated_turns | int | yes | session config |
| skills_primary | list | yes | embedding, UI, session summary |
| skills_secondary | list | yes | embedding |
| rubric | string | yes | critic prompt loading |
| persona | string | yes | roleplay prompt loading |
| persona_patience | enum | yes | human-readable diff check |
| setting | text | yes | roleplay system prompt |
| opening_line | string | yes | session start message to user |
| good_turn_examples | list | yes | critic prompt exemplars |
| bad_turn_examples | list | yes | critic prompt exemplars |
| common_mistakes | list | yes | rubric context |
| peers_skills | list | yes | clinical reporting |
| prerequisite_scenarios | list | yes | future LangGraph |
| unlocks_scenarios | list | yes | future LangGraph |
| recommended_next | string | yes | session summary UI |
| tags | list | yes | pgvector embedding string |
| reviewed | bool | yes | UI badge |
| notes | string | yes | author notes (never in prompts) |
