# AI Browser Agent

An autonomous AI agent that controls a real browser and real external services to complete tasks from natural language commands. It plans, uses tools, remembers state, and executes multi-step workflows — always with a human confirmation step before anything irreversible (submitting a form, sending an email).

## Stack

- **Frontend** — React 19, Vite, Tailwind CSS v4
- **Backend** — FastAPI, WebSockets, SQLite
- **Agent** — LangChain / LangGraph, Playwright, Groq API (`qwen/qwen3-32b` for the general agent, `llama-3.3-70b-versatile` for module LLM calls)
- **Modules** — `modules/form_filling/` (detect, fill, preview any web form), `modules/email_assistant/` (compose, draft, confirm, send via the Gmail API)

## Setup

```bash
# Python environment
python -m venv venv && source venv/bin/activate
pip install fastapi "uvicorn[standard]" sqlmodel aiosqlite \
            playwright langchain langchain-groq langgraph \
            groq google-api-python-client google-auth-httplib2 google-auth-oauthlib \
            python-dotenv beautifulsoup4 pytest
playwright install chromium

# Frontend
cd week6/ui && npm install && cd ../..

# API key
echo "GROQ_API_KEY=your_key_here" > .env
```

Get a free Groq API key at [console.groq.com](https://console.groq.com).

### Gmail API (for the email assistant module)

1. In Google Cloud Console, create a project and enable the Gmail API.
2. Configure the OAuth consent screen (External, add your account as a test user while unpublished) and create an OAuth client ID of type Desktop app.
3. Download the client secret JSON as `week5/credentials/client_secret.json` (the folder is gitignored — it also holds the cached auth token after the first run).
4. The first command that sends an email opens a browser window for the Google consent screen; after that the cached token makes future runs silent.

Recommended: use a separate dev Gmail account rather than a personal inbox.

## Running

```bash
# Terminal 1 — backend
source venv/bin/activate && cd week5 && uvicorn main:app --reload

# Terminal 2 — frontend
cd week6/ui && npm run dev   # → http://localhost:5173
```

Set `PLAYWRIGHT_HEADLESS=true` in `.env` to hide the browser window.

## Tests

```bash
python -m pytest modules/ week6/tests/ -v
```

## Progress

| Week | Topic | Output |
|---|---|---|
| 1 | Python + CSS selectors | Async profile reader, user profile schema |
| 2 | Playwright | Scraper, form filler, tab manager |
| 3 | LLMs + prompt engineering | Intent parser — NL → structured JSON |
| 4 | LangChain + agentic AI | ReAct agent with browser tools + memory |
| 5 | FastAPI + SQLite + WebSockets | REST API + live step streaming |
| 6 | React UI | Command bar, activity log, profile settings |

Build phase (Weeks 7–10):

| Module | Status | Output |
|---|---|---|
| 1 — Intelligent Form Filling | live-verified | Detects fields on any page (incl. iframes), fills from profile, generates long-text answers via LLM, retries on validation errors, remembers answers to previously-missing fields, uploads resumes, previews before submit |
| 2 — Email Assistant | live-verified (V1: draft/send/confirm) | Composes an email from a one-line intent via LLM, requires an explicit Send/Discard confirmation before the real Gmail API call — never auto-sends |
| 3 — Page & Content Summarisation | not started | |
| 4 — Google Calendar Intelligence | not started | |
| 5 — Cross-Module Commands | not started | |
| 6 — User Memory & Profile | partial | profile + learned-fields persistence from Week 5 / Module 1 |

See `CLAUDE.md` for full build-phase history and design decisions.
