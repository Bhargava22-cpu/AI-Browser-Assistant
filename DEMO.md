# Demo Script

A ~10 minute walkthrough of what's built so far: a general browser agent, plus two modules with a mandatory human-confirmation step before anything irreversible.

## Before you start

- `.env` has `GROQ_API_KEY` set.
- Gmail OAuth has already been authorized once (there's a cached `week5/credentials/token.json`). If not, run the email step below early and be ready to click through Google's consent screen yourself — don't do this live in front of an audience the first time.
- `week1/data/user_profile.json` / the seeded profile has realistic-looking data (name, email, phone, address, skills, resume path).

## Start the app

```bash
# Terminal 1 — backend
source venv/bin/activate && cd week5 && uvicorn main:app --reload

# Terminal 2 — frontend
cd week6/ui && npm run dev   # → http://localhost:5173
```

Open `http://localhost:5173`.

## Demo script

### 1. Profile (Profile tab)

Show the stored profile — name, email, phone, address, skills, resume path. This is what every module reads from; nothing is typed twice.

### 2. Module 1 — Intelligent Form Filling

Command bar:

```
fill the form at https://demoqa.com/automation-practice-form with my details
```

Talking points while it runs:
- The agent detects every field on the page (including ones inside iframes), maps them to the profile, and generates any free-text answers with an LLM.
- Each field shows up in the Activity Log as a structured row — filled (green), failed (red), or needing manual input (amber) — not a raw log line.
- It never clicks Submit. That's the point: a full-page screenshot preview is produced, and a human decides what happens next.
- If any field comes back "needs manual input," that's the ask-once-and-remember flow: answer it once via `POST /user/learned-fields`, and every future form fill uses that answer automatically — no LLM call needed for that field again.

### 3. Module 2 — Email Assistant

Command bar (use a real inbox you can check, or the dev test account):

```
email <recipient>@gmail.com and tell them the demo is going well
```

Talking points while it runs:
- The LLM drafts a subject and body grounded only in the profile — no invented facts.
- The task stops at `awaiting_confirmation`. Nothing has been sent yet.
- The Activity Log renders the draft as a card with the full subject/body and two buttons: **Send** and **Discard**.
- Click **Send** — this is the only code path in the whole app that ever calls the Gmail API. Click **Discard** on a second draft to show that path never touches Gmail at all (safe to demo mistakes).
- Check the recipient inbox to show the email actually arrived.

### 4. General agent (optional — shows the underlying ReAct loop)

Command bar:

```
go to google.com and search for AI news
```

This doesn't go through either module — it falls through to the general LangChain/LangGraph agent, which reasons step by step and drives the browser directly with `navigate` / `click` / `type_text` tools. Useful for showing the agent can still handle arbitrary commands outside the two built-out modules.

## Known rough edges (avoid live, or narrate around them)

- Phrasing like *"go to `<url>` and fill it out with my details"* (two actions chained in one sentence) currently breaks the intent parser. Use the single-action phrasing from step 2 instead.
- On demoqa's practice form specifically, the "Subjects" tag field and the "State" dropdown can occasionally report the wrong outcome — this is a known, documented issue, not a live bug to debug on stage.
- The first-ever email send on a machine will pop a real Google OAuth consent window. Do this once before the demo, not during it.

## Shut down

```bash
# find and stop both dev servers
lsof -i :8000 -sTCP:LISTEN
lsof -i :5173 -sTCP:LISTEN
kill <pid> <pid>
```
