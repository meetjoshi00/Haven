# /content/safety/safe_response.md

---
id: safe_response
version: 1
trigger: distress_keyword_match
llm_involved: false
reviewed: false
---

## What the user sees

---

### Heading shown on screen:
"Let's take a pause"

### Body text:
"It sounds like things might be feeling really hard right now.
That matters more than any scenario.

You don't have to be okay right now, and you don't have to
keep going with the practice session.

If you'd like to talk to someone who can help, here are some
options:"

### Resources shown (edit for your target region):

**If you're in crisis right now:**
- **Crisis Text Line** — Text HOME to 741741 (US, UK, Canada, Ireland)
- **International Association for Suicide Prevention** —
  https://www.iasp.info/resources/Crisis_Centres/
  (find your country's line)

**If you want to talk to someone:**
- **Samaritans (UK/Ireland)** — 116 123 (free, 24/7)
- **988 Suicide and Crisis Lifeline (US)** — call or text 988
- **Lifeline (Australia)** — 13 11 14

**If you're autistic and want to talk to someone who
understands:**
- **Autistic Self Advocacy Network** — autisticadvocacy.org
- **Autism Society helpline** — 1-800-328-8476

### Buttons shown:
- "I'm okay — take me back to the scenarios" → returns to
  scenario selection screen (NOT back into the same scenario)
- "Close the app for now" → closes session cleanly

---

## Design notes (for developer)

- Background: calm, muted — off-white or soft blue. No red.
- No animation, no sound.
- Font size: slightly larger than normal UI — 18px minimum.
- Do not auto-redirect. User must actively choose to return
  or leave.
- Do not log the specific keyword that triggered this screen
  to any analytics dashboard. Log only: {user_id, timestamp,
  event: "safe_screen_shown"}.
- Do not show this screen in a modal. It should be a full
  page replace — the roleplay content must not be visible
  behind it.
- After user clicks "I'm okay — take me back to scenarios":
  clear the current session, do not return to the same
  scenario, start fresh at scenario selection.

## Tone principles

- Warm, not clinical.
- No assumptions about what the user is experiencing.
- No instructions to "seek help immediately" — offer options,
  let the user choose.
- No mention of the AI system or the coaching app in this
  content — this screen is not about the app.
- Literal language throughout — no metaphors, no idioms.
  Autistic users may be in distress and literal language
  is more accessible.