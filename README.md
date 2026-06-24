# AI Browser Agent

An autonomous AI agent that controls a real browser to complete tasks from natural language commands. It plans, uses tools, remembers state, and executes multi-step workflows.

## Stack

- **Frontend** — React 19, Vite, Tailwind CSS v4
- **Backend** — FastAPI, WebSockets, SQLite
- **Agent** — LangChain / LangGraph, Playwright, Groq API (`qwen/qwen3-32b`)

## Setup

```bash
# Python environment
python -m venv venv && source venv/bin/activate
pip install fastapi "uvicorn[standard]" sqlmodel aiosqlite \
            playwright langchain langchain-groq langgraph \
            groq python-dotenv beautifulsoup4 pytest
playwright install chromium

# Frontend
cd week6/ui && npm install && cd ../..

# API key
echo "GROQ_API_KEY=your_key_here" > .env
```

Get a free Groq API key at [console.groq.com](https://console.groq.com).

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
python -m pytest week6/tests/ -v
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

Build phase (Weeks 7–10): form filling, email assistant, page summarisation, calendar integration, cross-module commands, user memory.
