import asyncio
import json
import os
from dotenv import load_dotenv
from groq import AsyncGroq, APIError

load_dotenv()

SYSTEM_PROMPT = """
You are an intent parser for an AI browser agent. Convert the user's natural language command into a structured JSON action plan.

Output ONLY valid JSON — no markdown, no explanation.

Schema:
{
  "action": "fill_form" | "navigate" | "email" | "summarize" | "click" | "calendar",
  "target_url": "<url or null>",
  "data": { <relevant key-value pairs or empty> },
  "steps": ["<step 1>", "<step 2>", ...]
}

For "calendar", data must include "schedule_request": the natural language scheduling
phrase verbatim (dates, times, recurrence, and any named invitees) — the calendar module
resolves relative dates and recurrence itself, so don't pre-parse it here.

If the command is ambiguous and cannot be resolved, output:
{
  "action": "clarify",
  "question": "<one clarifying question to ask the user>"
}

Few-shot examples:

User: go to linkedin.com and search for software engineer jobs
Output: {"action": "navigate", "target_url": "https://linkedin.com/jobs", "data": {"search_query": "software engineer"}, "steps": ["Open LinkedIn Jobs", "Type 'software engineer' in search bar", "Press Enter"]}

User: fill the internship application form with my details
Output: {"action": "fill_form", "target_url": null, "data": {"source": "user_profile"}, "steps": ["Detect all form fields on current page", "Load user profile", "Map profile fields to form fields", "Fill each field", "Show preview to user"]}

User: email my mentor that I submitted the application
Output: {"action": "email", "target_url": null, "data": {"recipient": "mentor", "subject": "Application Submitted", "body_intent": "inform mentor that application was submitted"}, "steps": ["Look up mentor contact", "Draft email body", "Show preview to user", "Send on confirmation"]}

User: summarize this page
Output: {"action": "summarize", "target_url": null, "data": {"scope": "current_page"}, "steps": ["Extract page content", "Send to LLM for summarization", "Return TL;DR and key points"]}

User: click the submit button
Output: {"action": "click", "target_url": null, "data": {"element": "submit button"}, "steps": ["Locate submit button on page", "Click it"]}

User: add DSA practice every day at 8pm for 2 weeks
Output: {"action": "calendar", "target_url": null, "data": {"schedule_request": "add DSA practice every day at 8pm for 2 weeks"}, "steps": ["Parse the scheduling request", "Resolve dates and recurrence", "Show event preview to user", "Create event on confirmation"]}
"""

TEST_COMMANDS = [
    "go to github.com and search for Python projects",
    "fill this job application form with my details",
    "email my mentor that I applied to the internship",
    "summarize the current page",
    "click the login button",
    "add DSA practice every day at 8pm for 2 weeks",
    "apply to this internship, add the deadline to calendar, email my mentor",
    "close all tabs",
    "do something useful",
    "send an email",
    "summarize this article and email it to my friend",
]


def _get_client() -> AsyncGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not set in .env")
    return AsyncGroq(api_key=api_key)


# Module-level client — created once, reused across all calls
_client: AsyncGroq = None


def _client_instance() -> AsyncGroq:
    global _client
    if _client is None:
        _client = _get_client()
    return _client


async def parse_intent(user_command: str) -> dict:
    response = await _client_instance().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_command},
        ],
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if model wraps output
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {e}\nRaw: {raw}")


async def main():
    print("=" * 60)
    print("INTENT PARSER — 10 TEST COMMANDS")
    print("=" * 60)

    for i, command in enumerate(TEST_COMMANDS, 1):
        print(f"\n[{i}] Command: \"{command}\"")
        try:
            result = await parse_intent(command)
            print(f"    Action  : {result.get('action')}")
            if result.get("action") == "clarify":
                print(f"    Question: {result.get('question')}")
            else:
                if result.get("target_url"):
                    print(f"    URL     : {result.get('target_url')}")
                if result.get("steps"):
                    for step in result["steps"]:
                        print(f"            - {step}")
        except ValueError as e:
            print(f"    Parse error: {e}")
        except EnvironmentError as e:
            print(f"    Config error: {e}")
            break
        except APIError as e:
            print(f"    Groq API error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
