# AI Browser Agent — Architecture

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       React UI (Vite)                        │
│                                                                │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────────┐ │
│  │ CommandBar  │   │ ActivityLog  │   │  ProfileSettings    │ │
│  │POST /command│   │ WS /ws/{id}  │   │ GET/POST /user/     │ │
│  │             │   │ + GET/POST   │   │   profile            │ │
│  │             │   │ /email/drafts│   │ GET/POST /user/     │ │
│  │             │   │      /*      │   │   learned-fields     │ │
│  └──────┬──────┘   └──────┬───────┘   └──────────┬──────────┘ │
└─────────┼──────────────────┼──────────────────────┼───────────┘
          │ HTTP/REST         │ WebSocket + HTTP/REST  │ HTTP/REST
          ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Backend (uvicorn, week5/)               │
│                                                                │
│  agent_runner.run_agent_task (background task, per command)   │
│    → routes on intent_parser's action (see routing diagram)   │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                 SQLite (agent.db)                      │    │
│  │  Task: task_id, command, status, steps                 │    │
│  │  UserProfile: name, email, phone, …, learned_fields     │    │
│  │  EmailDraft: draft_id, task_id, to/subject/body, status │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────┬─────────────────┘
                            ▼                  ▼
                    Playwright Browser     Gmail API (OAuth)
                    (Module 1 — form       (Module 2 — email
                     filling)               assistant)
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
   │                            never clicks submit — Task.status → completed
   │
   ├─ action == "email" ─────▶ modules/email_assistant
   │                            compose via AsyncGroq (no thread hop)
   │                            → EmailDraft row created, Task.status → awaiting_confirmation
   │                            → human clicks Send/Discard in ActivityLog
   │                            → POST /email/drafts/{id}/send → Gmail API send
   │                              (only path that ever calls the Gmail API — never automatic)
   │
   └─ else ──────────────────▶ general LangGraph AgentExecutor
                                ReAct loop: Groq LLM (qwen3) ⇄ browser tools
                                (navigate / click / type_text), MemorySaver per
                                thread_id, run_in_executor + BrowserWorker thread
```

## Data Flow — Command Execution

1. User types a command in **CommandBar** → `POST /command`
2. FastAPI creates a **Task** row in SQLite, queues an `asyncio.Queue`, starts `agent_runner.run_agent_task` as a **background task**
3. UI opens a **WebSocket** to `/ws/{task_id}`
4. `agent_runner` first calls `intent_parser` and routes to `modules/form_filling`, `modules/email_assistant`, or the general LangGraph agent based on the parsed action
5. Each step is pushed to the **asyncio.Queue** (WebSocket) and persisted to **SQLite** simultaneously
6. **ActivityLog** receives each step and renders it live — form-filling and email steps render as structured outcome rows, not raw log lines; final `done` message closes the socket
7. If the WebSocket reconnects after task completion, steps are **replayed from SQLite**

## Data Flow — Email Draft & Confirm

1. `modules/email_assistant.compose_email` drafts a subject/body via LLM, grounded in the user profile; the module never calls the Gmail API itself
2. The draft is persisted as an **EmailDraft** row (`status = pending_confirmation`); `Task.status` becomes `awaiting_confirmation`, not `completed`
3. **ActivityLog** detects the "Draft ready" step, fetches the full draft via `GET /email/drafts/{id}`, and renders it with **Send** / **Discard** buttons
4. Only a human clicking **Send** triggers `POST /email/drafts/{id}/send` → `modules/email_assistant.send_email` → the real Gmail API call (OAuth via `google-auth-oauthlib`, scope `gmail.send` only)
5. **Discard** (`POST /email/drafts/{id}/discard`) marks the draft dead without ever touching the Gmail API
6. Either action appends a step to the original **Task** and resolves its status to `completed` or `failed`

## External APIs

```
modules/email_assistant → Gmail API           (Module 2 — Email Assistant, live)
AgentExecutor            → Google Calendar API (Module 4 — Calendar Intelligence, not started)
```
