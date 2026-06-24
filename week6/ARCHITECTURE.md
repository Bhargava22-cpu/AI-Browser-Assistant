# AI Browser Agent — Architecture

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     React UI (Vite)                     │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ CommandBar  │  │ ActivityLog  │  │ProfileSettings│  │
│  │ POST/command│  │ WS /ws/{id}  │  │GET/POST       │  │
│  └──────┬──────┘  └──────┬───────┘  │/user/profile  │  │
│         │                │          └───────┬───────┘  │
└─────────┼────────────────┼─────────────────┼───────────┘
          │  HTTP/REST      │  WebSocket       │  HTTP/REST
          ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend (uvicorn)                 │
│                                                         │
│  POST /command    →  creates Task in SQLite             │
│  GET  /status/:id →  returns Task + steps from SQLite   │
│  WS   /ws/:id     →  streams live steps via asyncio.Queue│
│  GET  /user/profile  →  reads UserProfile from SQLite   │
│  POST /user/profile  →  upserts UserProfile in SQLite   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │             agent_runner (background task)        │   │
│  │                                                   │   │
│  │  run_in_executor → BrowserWorker thread           │   │
│  │                                                   │   │
│  │  ┌────────────────────────────────────────────┐   │   │
│  │  │           AgentExecutor (LangGraph)         │   │   │
│  │  │                                             │   │   │
│  │  │  ┌──────────┐   ReAct loop   ┌───────────┐  │   │   │
│  │  │  │ Groq LLM │ ─────────────▶ │  Tools    │  │   │   │
│  │  │  │ (qwen3)  │ ◀─────────────  │ navigate  │  │   │   │
│  │  │  └──────────┘   observe      │ click     │  │   │   │
│  │  │                              │ type_text │  │   │   │
│  │  │  ┌──────────┐                └─────┬─────┘  │   │   │
│  │  │  │MemorySaver│                     │        │   │   │
│  │  │  │(per thread│                     ▼        │   │   │
│  │  │  │    id)    │           ┌──────────────────┐│   │   │
│  │  │  └──────────┘           │ Playwright Browser││   │   │
│  │  └────────────────────────────────────────────┘│   │   │
│  └──────────────────────────────────────────────┘ │   │   │
│                                    └───────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │              SQLite (agent.db)                    │   │
│  │   Task table: task_id, command, status, steps     │   │
│  │   UserProfile table: name, email, phone, …        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Data Flow — Command Execution

1. User types a command in **CommandBar** → `POST /command`
2. FastAPI creates a **Task** row in SQLite, queues an `asyncio.Queue`, starts agent as a **background task**
3. UI opens a **WebSocket** to `/ws/{task_id}`
4. `agent_runner` runs the LangGraph agent in a thread pool via `run_in_executor`
5. Each agent step is pushed to the **asyncio.Queue** (WebSocket) and persisted to **SQLite** simultaneously
6. **ActivityLog** receives each step and renders it live; final `done` message closes the socket
7. If the WebSocket reconnects after task completion, steps are **replayed from SQLite**

## External APIs (Weeks 7–10)

```
AgentExecutor → Gmail API   (Module 2 — Email Assistant)
             → Google Calendar API (Module 4 — Calendar Intelligence)
```
