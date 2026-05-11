# Layer 3 — Social Coaching Chatbot Spec

## RAG pipeline

Every user turn flows through:
```
distress check → intent classify → route → respond
```

### Distress check (always first)
- Case-insensitive substring match against /content/safety/distress_keywords.yaml
- Categories: self_harm, suicidal_ideation, crisis_overwhelm, abuse_disclosure
- Match → full-page safe_response screen. No LLM call. No logging.
- Return from safe screen → clear session → scenario selection (not same scenario)

### Intent classification
Fast Groq call, no retrieval. System prompt:
```
Classify into exactly one category. Respond with only the category name.

DISTRESS - crisis, self-harm, suicidal ideation, acute overwhelm, abuse disclosure
OFF_TOPIC - unrelated to current scenario or social skills practice
SCENARIO_QUESTION - question about the scenario, what to practice, how system works
ROLEPLAY_TURN - response to persona, attempt at scenario, continuation of roleplay

Message: {user_text}
```

### Routing (LangChain RunnableBranch)
```
DISTRESS    → immediate safe_response screen. No LLM. No logging.
OFF_TOPIC   → templated redirect. No retrieval.
SCENARIO_Q  → answer from scenario frontmatter only. No roleplay call.
ROLEPLAY    → full roleplay chain (below)
```

### Roleplay chain
```
1. Memory retrieval
   pgvector similarity on coaching_sessions.summary_embedding
   WHERE user_id = {user_id}, cosine >= 0.75, top-3
   Below threshold → skip memory injection

2. Load content files (by ID from frontmatter, NOT semantic search)
   Scenario: /content/scenarios/{scenario_id}.md
   Persona: /content/personas/{persona_id}.md
   Rubric: /content/rubrics/{rubric_id}.md

3. Prompt assembly
   System A (roleplay):
     You are {persona.name}. {persona.description}
     Patience level: {persona.patience_level}
     Setting: {scenario.setting}
     Respond in character. Max 2 sentences.
     Off-topic → "Let's stay in the scenario — what would you say next?"
     Never break character to explain you are AI.
     {memory_context if available}

   System B (critic):
     Evaluating a social skills practice response.
     Rubric: {rubric.scoring_criteria}
     Respond ONLY with valid JSON:
     {"score": <1-5>, "suggestion": "<one sentence>"}
     No markdown. No preamble.

4. Parallel calls (RunnableParallel + asyncio)
   Call A → Groq Llama 3.3 70B → persona reply
   Call B → Groq Llama 3.3 70B → critic JSON
   Both use .with_fallbacks([gemini_chain])
   JsonOutputParser on critic with one auto-retry on parse failure
   Safe default on second failure: {"score": 3, "suggestion": ""}

5. Memory write
   Append turn to coaching_turns table
   Update coaching_sessions.turn_count
   turn_count >= max_turns → trigger session end

6. Session end
   LLM call: summarise session in 2-3 sentences
   Embed summary with all-MiniLM-L6-v2
   Store: summary, summary_embedding, avg_score, ended_at, completed=true
```

### LangChain components used
RunnableBranch, RunnableParallel, RunnableSequence, PGVector retriever,
JsonOutputParser, ConversationBufferMemory, .with_fallbacks()

### Tracing
LangSmith: LANGCHAIN_TRACING_V2=true, LANGCHAIN_PROJECT=asd-coaching-layer3

---

## Critic output schema [LOCKED — additive only]
```json
{"score": 3, "suggestion": "..."}
```
UI must use optional chaining on all fields.
Future fields (tone, strengths, better_phrasing) — do not build yet.

---

## Session memory [LOCKED]
- Cross-session from day 1
- Stored in Supabase Postgres coaching_sessions table — NOT LangChain memory objects
- On end: summarise → embed (all-MiniLM-L6-v2) → store summary_embedding VECTOR(384)
- On start: retrieve top-3 past summaries by cosine similarity

---

## API endpoints

```
POST /coach/session/start
     body: {user_id, scenario_id}
     returns: {session_id, opening_line, scenario_title}

POST /coach/session/turn
     body: {session_id, user_text}
     returns: {intent, persona_reply, critic, turn_number,
               turns_remaining, session_complete}

POST /coach/session/end
     body: {session_id}
     returns: {summary, avg_score, skills_practiced}

GET  /coach/scenarios
     params: domain?, difficulty?, tags?
     returns: [{id, title, domain, difficulty, skills_primary,
                estimated_turns, reviewed}]

GET  /coach/scenarios/{id}
     returns: full scenario frontmatter (no examples — those stay server-side)
```

---

## Content — scenarios (30 total)

### Social (12)
| ID | Title | Diff |
|---|---|---|
| social_001 | Ordering a coffee | 1 |
| social_002 | Asking for directions from a stranger | 1 |
| social_003 | Thanking someone for help | 1 |
| social_004 | Greeting a neighbour | 1 |
| social_005 | Returning a faulty item to a shop | 2 |
| social_006 | Asking to sit next to someone on a bench | 2 |
| social_007 | Making a phone call to book an appointment | 2 |
| social_008 | Joining an ongoing conversation | 2 |
| social_009 | Disagreeing politely with a friend | 3 |
| social_010 | Declining an invitation | 3 |
| social_011 | Handling a misunderstanding with a stranger | 3 |
| social_012 | Giving a compliment and responding to one | 3 |

### Sensory (8)
| ID | Title | Diff |
|---|---|---|
| sensory_001 | Asking someone to lower their music volume | 1 |
| sensory_002 | Requesting a quieter table in a restaurant | 1 |
| sensory_003 | Telling a friend about a sensory need | 1 |
| sensory_004 | Explaining sensory needs to a teacher | 2 |
| sensory_005 | Advocating for space in a crowded environment | 2 |
| sensory_006 | Asking for a sensory break during an activity | 2 |
| sensory_007 | Explaining overwhelm to a colleague | 3 |
| sensory_008 | Requesting workplace sensory accommodation | 3 |

### Workplace/School (10)
| ID | Title | Diff |
|---|---|---|
| workplace_001 | Asking a teacher a question after class | 1 |
| workplace_002 | Introducing yourself to a classmate | 1 |
| workplace_003 | Asking for help on a task from a colleague | 1 |
| workplace_004 | Asking for a deadline extension | 2 |
| workplace_005 | Joining a group project | 2 |
| workplace_006 | Giving feedback on a colleague's work | 2 |
| workplace_007 | Receiving criticism gracefully | 2 |
| workplace_008 | Basic job interview — introducing yourself | 3 |
| workplace_009 | Disagreeing with a manager respectfully | 3 |
| workplace_010 | Asking for formal accommodations | 3 |

Difficulties: 1=patient persona, 2=neutral, 3=realistic/mildly impatient.
Default turns per session: 12 (min 6, hard cap 16).

---

## Content — personas (7)

| ID | Used in | Patience | Difficulty |
|---|---|---|---|
| barista_rushed | social_001 | high | 1 |
| stranger_helpful | social_002-004, sensory_001-003 | high | 1 |
| shop_assistant | social_005-006 | medium | 2 |
| friend_casual | social_007-008, sensory_003 | high | 1-2 |
| teacher_patient | sensory_004, workplace_001-003 | high | 1-2 |
| colleague_friendly | sensory_005-007, workplace_004-007 | medium | 2-3 |
| interviewer_formal | workplace_008-010, social_009-012, sensory_008 | low | 3 |

---

## Content — rubrics (COMPLETE, do not regenerate)
- /content/rubrics/social_basic.md
- /content/rubrics/social_advanced.md
- /content/rubrics/sensory_advocacy.md
- /content/rubrics/workplace_communication.md

Each: 5-level scoring criteria, 2 examples per level, Milton 2012 framing.

---

## Content — safety (COMPLETE, do not regenerate)
- /content/safety/distress_keywords.yaml — self_harm, suicidal_ideation, crisis_overwhelm, abuse_disclosure
- /content/safety/safe_response.md — heading, body, crisis resources, button labels, UI behaviour notes

---

## Scenario frontmatter key fields
- `difficulty` → determines persona patience
- `rubric` → which rubric file loads for critic
- `persona` → which persona file loads for roleplay
- `version` → increment on content change → triggers re-indexing
- `prerequisite_scenarios` → future routing
- `unlocks_scenarios` → future routing

Full schema: /content/schema/scenario_schema.md

---

## Indexing (/scripts/index_scenarios.py)
1. Read all /content/scenarios/*.md
2. Extract frontmatter metadata
3. Embed: title + domain + tags + skills_primary (concatenated)
4. Upsert to Supabase: only re-embed if version changed
5. Store: scenario_id, embedding VECTOR(384), metadata JSON

---

## UI — functional requirements

### Accessibility constraints [LOCKED]
- WCAG 2.2 AA minimum
- prefers-reduced-motion respected — no auto-animation
- Sensory-friendly palette: off-white #F7F5F1, no saturated reds, no auto-sound
- Literal button labels (e.g. "Tell my caregiver I'm overloaded" not "Send alert")
- Atkinson Hyperlegible preferred font (user-selectable)
- Two route groups: /app/(user)/ and /app/(caregiver)/

### Screens needed

**Scenario selection** — browse/filter scenarios by domain and difficulty, start a session.

**Active coaching session** — chat interface for persona roleplay, real-time critic feedback (score + suggestion), turn counter, text input. Persona reply should feel immediate; critic can load async.

**Session summary** — avg score, skills practiced, narrative summary. Navigation to try another scenario.

**Distress safe-response** — full-page replace (never modal), no background content visible, no animation, content from safe_response.md, min 18px font. Return clears session → scenario selection.

**Caregiver dashboard** — shell for demo. Alert feed via Supabase Realtime. Each alert: headline, why, recommended_actions, acknowledge/false-alarm actions.

### Component structure
```
app/(user)/coaching/
├── page.tsx                    # scenario selection
├── [sessionId]/
│   ├── page.tsx                # active session
│   └── summary/page.tsx        # session end
└── safe-response/page.tsx      # distress screen

app/(caregiver)/
├── dashboard/page.tsx
└── alerts/page.tsx
```
