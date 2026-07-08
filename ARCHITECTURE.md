# AI Browser Agent — Architecture

## Project Evolution — Week 1 → Now

Each week's checkpoint built directly on the last; nothing below was thrown away, only
wrapped by the next layer. Week 6 reached the target architecture from `CLAUDE.md`
(`React UI → FastAPI → AgentExecutor → [LLM, Browser Tools, Memory] → External APIs`);
Week 7 is the same shape with `intent_parser` now routing to purpose-built pipelines
instead of everything going through the agent. Week 7 continued (current, build phase)
adds a second path into those same pipelines: the general agent can now call them
directly as tools, so compound commands aren't limited to whatever `intent_parser`
classified as a single action.

```
Week 1 — Python fundamentals
┌────────────────────────────────────────────────────┐
│ read_profile.py — async JSON reader                │
│ No browser. No LLM. No server.                      │
└────────────────────────────────────────────────────┘
                    │
                    │  adds browser automation
                    ▼
Week 2 — Playwright
┌────────────────────────────────────────────────────┐
│ navigator.py / form_filler.py / tab_manager.py      │
│ Standalone async scripts driving a real Chromium    │
│ browser. Still no LLM, no server.                   │
└────────────────────────────────────────────────────┘
                    │
                    │  adds the "brain" (still disconnected)
                    ▼
Week 3 — LLM intent parsing
┌────────────────────────────────────────────────────┐
│ intent_parser.py (Groq)                             │
│ NL command -> structured {action, target_url,       │
│ data, steps} JSON. Not wired to the browser yet.    │
└────────────────────────────────────────────────────┘
                    │
                    │  wires LLM + browser into one loop
                    ▼
Week 4 — LangChain / LangGraph agent
┌────────────────────────────────────────────────────┐
│ ReAct agent: navigate_to / click_element /          │
│ type_text tools (wraps Week 2's Playwright)         │
│ + conversation memory (MemorySaver).                │
│ First real "agent", not just scripts.               │
└────────────────────────────────────────────────────┘
                    │
                    │  adds a server + persistence
                    ▼
Week 5 — FastAPI + SQLite + WebSockets
┌────────────────────────────────────────────────────┐
│ Wraps the Week 4 agent as a background task.        │
│ POST /command, GET /status, WS /ws/{id}.            │
│ Task + UserProfile persisted to SQLite.             │
└────────────────────────────────────────────────────┘
                    │
                    │  adds the UI
                    ▼
Week 6 — React UI  (Checkpoint 4: target architecture reached)
┌────────────────────────────────────────────────────┐
│ React UI -> FastAPI -> AgentExecutor ->             │
│   [LLM, Browser Tools, Memory]                      │
│   -> External APIs (Gmail, Calendar)                │
│ CommandBar / ActivityLog / ProfileSettings          │
│ talk to Week 5's backend via REST + WebSocket.      │
└────────────────────────────────────────────────────┘
                    │
                    │  intent_parser stops just describing,
                    │  starts ROUTING to purpose-built pipelines
                    ▼
Week 7 — Build Phase
┌────────────────────────────────────────────────────┐
│ action == "fill_form" -> modules/form_filling       │
│   (deterministic pipeline, 2 LLM calls)             │
│ action == "email"     -> modules/email_assistant    │
│   (deterministic pipeline, 1 LLM call)              │
│ else                  -> Week 4 LangGraph agent     │
│   (unchanged - general browsing fallback)           │
│                                                      │
│ + EmailDraft table, learned_fields column           │
│ + Gmail OAuth (first real external API)             │
│ + UI restyled; ActivityLog renders structured       │
│   per-field outcome rows, not raw log lines         │
└────────────────────────────────────────────────────┘
                    │
                    │  the general agent gets the SAME module
                    │  capabilities as tools, not just intent-routing
                    ▼
Week 7 continued — Agent Tools + Module 4 (current)
┌────────────────────────────────────────────────────┐
│ fill_form_tool / compose_email_draft_tool /         │
│ create_calendar_draft_tool / get_page_text added    │
│ to the general LangGraph agent's toolset, so a       │
│ compound command ("fill this form AND email X")     │
│ can chain modules — intent-routing still handles    │
│ the fast, single-action common case unchanged.      │
│                                                      │
│ + modules/calendar_assistant (Module 4): NL          │
│   scheduling -> RRULE, draft/confirm/discard,        │
│   own Calendar OAuth token (separate from Gmail's)  │
│ + CalendarEventDraft table                          │
│ + Email "suggest changes" revise-in-place flow       │
│ + Form-filler chat-style reply flow: missing         │
│   fields surface as an inline question in the        │
│   Activity Log; a natural-language reply fills       │
│   them on the still-open live page                   │
│ + UI redesign v2: dark hero panel, capability        │
│   chips, inline SVG icon set                         │
└────────────────────────────────────────────────────┘
```

## Component Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                          React UI (Vite)                            │
│                                                                       │
│ ┌───────────┐ ┌────────────────────────┐ ┌─────────────────────┐   │
│ │ CommandBar│ │      ActivityLog        │ │   ProfileSettings   │   │
│ │POST       │ │ WS /ws/{id}              │ │ GET/POST /user/     │   │
│ │/command   │ │ + GET/POST /email/drafts│ │   profile            │   │
│ │           │ │      /*                  │ │ GET/POST /user/     │   │
│ │           │ │ + GET/POST /calendar/    │ │   learned-fields     │   │
│ │           │ │      drafts/*            │ │                      │   │
│ │           │ │ + POST /tasks/{id}/reply │ │                      │   │
│ └─────┬─────┘ └───────────┬──────────────┘ └──────────┬───────────┘   │
└───────┼───────────────────┼──────────────────────────┼───────────────┘
        │ HTTP/REST          │ WebSocket + HTTP/REST      │ HTTP/REST
        ▼                    ▼                            ▼
┌───────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (uvicorn, week5/)                  │
│                                                                       │
│  agent_runner.run_agent_task (background task, per command)         │
│    → routes on intent_parser's action (see routing diagram)         │
│    → fast paths: form_filling / email / calendar                    │
│    → fallback: general LangGraph agent, which ALSO has              │
│      fill_form_tool / compose_email_draft_tool /                    │
│      create_calendar_draft_tool / get_page_text as tools            │
│      (compound commands can chain modules here)                     │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │                     SQLite (agent.db)                       │     │
│  │  Task: task_id, command, status, steps                      │     │
│  │  UserProfile: name, email, phone, …, learned_fields          │     │
│  │  EmailDraft: draft_id, task_id, to/subject/body, status      │     │
│  │  CalendarEventDraft: draft_id, task_id, title/start/end/      │     │
│  │    recurrence/attendees, status                              │     │
│  └───────────────────────────────────────────────────────────┘     │
└───────────────────┬───────────────────┬───────────────┬─────────────┘
                     ▼                   ▼               ▼
             Playwright Browser     Gmail API        Google Calendar API
             (Module 1 — form       (OAuth,           (OAuth, own token —
              filling; also read    Module 2)          Module 4)
              by get_page_text)
```

## Task Routing — `agent_runner.run_agent_task`

```
command
   │
   ▼
intent_parser (Groq llama-3.3-70b)  →  {action, data}
   │
   ├─ action == "fill_form" ──▶ modules/form_filling
   │                            detect → map → generate → fill → upload → preview
   │                            (sync pipeline, run_in_executor + BrowserWorker thread)
   │                            never clicks submit
   │                            missing fields → Task.status → awaiting_input
   │                              → human replies in ActivityLog's inline ask card
   │                              → POST /tasks/{id}/reply → modules.form_filling
   │                                .answer_missing_fields (matches reply to fields
   │                                via LLM, fills them on the SAME still-open page)
   │                            no missing fields → Task.status → completed
   │
   ├─ action == "email" ─────▶ modules/email_assistant
   │                            compose via AsyncGroq (no thread hop)
   │                            → EmailDraft row created, Task.status → awaiting_confirmation
   │                            → human can request changes (POST /email/drafts/{id}/revise
   │                              → re-composes the SAME draft in place, still pending)
   │                            → human clicks Send/Discard in ActivityLog
   │                            → POST /email/drafts/{id}/send → Gmail API send
   │                              (only path that ever calls the Gmail API — never automatic)
   │
   ├─ action == "calendar" ──▶ modules/calendar_assistant
   │                            parse_schedule_intent via AsyncGroq — resolves relative
   │                            dates/recurrence into ISO datetimes + an RRULE
   │                            → CalendarEventDraft row created, Task.status →
   │                              awaiting_confirmation
   │                            → human clicks Confirm/Discard in ActivityLog
   │                            → POST /calendar/drafts/{id}/confirm → Calendar API
   │                              create (sends invites if attendees given) — only
   │                              path that ever calls the Calendar API
   │
   └─ else ──────────────────▶ general LangGraph AgentExecutor
                                ReAct loop: Groq LLM (qwen3) ⇄ tools —
                                navigate_to / click_element / type_text / get_page_text
                                (raw browser control) PLUS fill_form_tool /
                                compose_email_draft_tool / create_calendar_draft_tool
                                (same module pipelines above, callable mid-conversation
                                so one compound command can chain them). Per-task
                                context (profile, step_callback, draft-creation
                                callbacks) injected via RunnableConfig["configurable"].
                                MemorySaver per thread_id, run_in_executor +
                                BrowserWorker thread. Only the two email/calendar
                                *draft* tools are exposed — send/create stay behind
                                the explicit confirm routes above, never automatic.
```

## Data Flow — Command Execution

1. User types a command in **CommandBar** → `POST /command`
2. FastAPI creates a **Task** row in SQLite, queues an `asyncio.Queue`, starts `agent_runner.run_agent_task` as a **background task**
3. UI opens a **WebSocket** to `/ws/{task_id}`
4. `agent_runner` first calls `intent_parser` and routes to `modules/form_filling`, `modules/email_assistant`, `modules/calendar_assistant`, or the general LangGraph agent (which itself may call any of those three module pipelines as tools) based on the parsed action
5. Each step is pushed to the **asyncio.Queue** (WebSocket) and persisted to **SQLite** simultaneously
6. **ActivityLog** receives each step and renders it live — form-filling, email, and calendar steps render as structured outcome rows, not raw log lines; final `done` message closes the socket
7. If the WebSocket reconnects after task completion, steps are **replayed from SQLite**

## Data Flow — Email Draft, Revise & Confirm

1. `modules/email_assistant.compose_email` drafts a subject/body via LLM, grounded in the user profile; the module never calls the Gmail API itself
2. The draft is persisted as an **EmailDraft** row (`status = pending_confirmation`); `Task.status` becomes `awaiting_confirmation`, not `completed`
3. **ActivityLog** detects the "Draft ready" step, fetches the full draft via `GET /email/drafts/{id}`, and renders it with **Send** / **Discard** buttons plus a "Suggest changes" feedback box
4. Typing feedback and submitting calls `POST /email/drafts/{id}/revise` → `agent_runner.revise_email_draft` → `compose_email(revise_from=..., feedback=...)` re-composes the SAME draft row in place (same `draft_id`, still `pending_confirmation`) — no Gmail API call, still needs Send/Discard afterward
5. Only a human clicking **Send** triggers `POST /email/drafts/{id}/send` → `modules/email_assistant.send_email` → the real Gmail API call (OAuth via `google-auth-oauthlib`, scope `gmail.send` only)
6. **Discard** (`POST /email/drafts/{id}/discard`) marks the draft dead without ever touching the Gmail API
7. Either terminal action appends a step to the original **Task** and resolves its status to `completed` or `failed`

## Data Flow — Calendar Draft & Confirm

1. `modules/calendar_assistant.parse_schedule_intent` resolves a natural-language scheduling phrase into concrete ISO datetimes plus an RFC5545 `RRULE` (if recurring) via LLM, grounded in the current date/time and timezone; the module never calls the Calendar API itself
2. The draft is persisted as a **CalendarEventDraft** row (`status = pending_confirmation`); `Task.status` becomes `awaiting_confirmation`
3. **ActivityLog** detects the "Draft ready" step, fetches the full draft via `GET /calendar/drafts/{id}`, and renders it (title, start/end, recurrence, invitees) with **Confirm** / **Discard** buttons
4. Only a human clicking **Confirm** triggers `POST /calendar/drafts/{id}/confirm` → `modules/calendar_assistant.create_event` → the real Calendar API call (OAuth scope `calendar.events` only, own token separate from Gmail's) — sends invite emails automatically if attendees were given
5. **Discard** (`POST /calendar/drafts/{id}/discard`) marks the draft dead without ever touching the Calendar API
6. Either terminal action appends a step to the original **Task** and resolves its status to `completed` or `failed`

## Data Flow — Form-Filler Chat Follow-Up

1. `modules/form_filling.fill_form` reports fields it couldn't map to the profile as `missing_fields`; `agent_runner` stashes them in an in-memory `_pending_field_prompts[task_id]` (tied to the live `BrowserWorker` page, not persisted to SQLite) and sets `Task.status` to `awaiting_input`
2. **ActivityLog** renders the `[ask]` step as an inline question card (`FormFillAskCard`) with a free-text reply box
3. Submitting a reply calls `POST /tasks/{task_id}/reply` → `agent_runner.answer_task_reply` → `modules/form_filling.answer_missing_fields`, which matches the reply against the pending fields via LLM (`reply_matcher.match_reply_to_fields`) and fills whatever it answers directly on the **same still-open live page**
4. Matched answers are persisted to `UserProfile.learned_fields` so future forms don't ask again; fields the reply didn't address stay pending and `Task.status` stays `awaiting_input`; once none remain, `Task.status` becomes `completed`

## External APIs

```
modules/email_assistant    → Gmail API           (Module 2 — Email Assistant, live)
modules/calendar_assistant → Google Calendar API  (Module 4 — Calendar Intelligence, live)
```
