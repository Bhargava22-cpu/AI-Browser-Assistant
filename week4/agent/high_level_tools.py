"""LangChain tool wrappers around the modules/ packages (form_filling, email_assistant,
calendar_assistant), so the general-purpose agent can chain them with the raw browser
primitives in tools.py to satisfy cross-module commands (Module 5).

Email SENDING and calendar event CREATION are deliberately not exposed as tools here —
only drafting is. Actually sending/creating only ever happens via the explicit
POST /email/drafts/{id}/send or POST /calendar/drafts/{id}/confirm routes, so the agent
can never take either externally-visible action without the user clicking a button in the UI.

All three tools read per-task state (profile, step_callback, and per-module draft-creation
callbacks) from RunnableConfig["configurable"], injected by week5/agent_runner.py when it
invokes the agent. LangChain auto-populates a `config: RunnableConfig` parameter without
exposing it in the tool's schema, so the LLM never sees or has to supply it.
"""

import asyncio
import sys
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.calendar_assistant import describe_event_ready, parse_schedule_intent  # noqa: E402
from modules.email_assistant import compose_email, describe_draft_ready  # noqa: E402
from modules.form_filling import describe_fill_result, fill_form  # noqa: E402
from tools import get_worker  # noqa: E402


def _configurable(config: RunnableConfig) -> dict:
    return (config or {}).get("configurable", {})


@tool
def fill_form_tool(target_url: str, config: RunnableConfig) -> str:
    """Detect and fill in the form on a webpage using the user's saved profile.
    Pass target_url to navigate there first, or an empty string to fill whatever
    page the browser is already on. Never submits the form — only fills fields
    and builds a preview. Returns a summary of what was filled, what still needs
    the user's input, and where the preview screenshot was saved."""
    cfg = _configurable(config)
    profile = cfg.get("profile")
    step_callback = cfg.get("step_callback")
    task_id = cfg.get("thread_id", "unknown")
    if profile is None:
        return "Cannot fill form: no user profile available in this context."

    def emit(msg: str) -> None:
        if step_callback:
            step_callback(f"[form_filling] {msg}")

    def emit_warning(msg: str) -> None:
        if step_callback:
            step_callback(f"[form_filling][warning] {msg}")

    emit("Detecting fields and mapping to profile...")
    result = fill_form(get_worker(), profile, task_id, url=target_url or None)

    lines = describe_fill_result(result)
    for line in lines:
        emit(line)

    for warning in result.warnings:
        emit_warning(warning)

    summary = "\n".join(f"- {line}" for line in lines) if lines else "No fields were filled."
    return f"Form fill complete on {result.url}.\n{summary}\nThe form was NOT submitted."


@tool
def compose_email_draft_tool(recipient: str, body_intent: str, subject_hint: str, config: RunnableConfig) -> str:
    """Draft an email to a literal email address (not a name — resolve names to an
    address first, or ask the user). Composes a subject and body via LLM grounded in
    the user's profile and saves it as a pending draft. Pass an empty string for
    subject_hint to let the LLM choose the subject. This tool NEVER sends the email —
    sending only happens after the user explicitly clicks Send in the UI. Always tell
    the user the email is drafted and awaiting their confirmation, never that it was
    sent."""
    cfg = _configurable(config)
    profile = cfg.get("profile")
    step_callback = cfg.get("step_callback")
    create_draft_fn = cfg.get("create_draft_fn")
    if profile is None or create_draft_fn is None:
        return "Cannot draft email: no user profile/draft store available in this context."

    def emit(msg: str) -> None:
        if step_callback:
            step_callback(f"[email] {msg}")

    emit(f"Composing message to {recipient}...")
    try:
        draft_plan = asyncio.run(compose_email(profile, recipient, body_intent, subject_hint or None))
    except ValueError as e:
        emit(f"FAILED to compose: {e}")
        return f"Could not draft the email: {e}"

    draft = create_draft_fn(draft_plan.to_email, draft_plan.subject, draft_plan.body)
    emit(describe_draft_ready(draft.to_email, draft.subject, draft.draft_id))
    return (
        f"Drafted an email to {draft.to_email} (subject: '{draft.subject}'), "
        f"draft_id={draft.draft_id}. It has NOT been sent — it is waiting for the "
        "user to review and click Send in the UI."
    )


@tool
def create_calendar_draft_tool(schedule_request: str, config: RunnableConfig) -> str:
    """Draft a calendar event from a natural language scheduling request (e.g. "add
    DSA practice every day at 8pm for 2 weeks", "schedule a call with Priya tomorrow
    at 3pm"). Pass the scheduling phrase through close to verbatim — this tool resolves
    relative dates and recurrence itself, don't pre-parse them. Saves it as a pending
    draft. This tool NEVER creates the actual calendar event — creation only happens
    after the user explicitly clicks Confirm in the UI. Always tell the user the event
    is drafted and awaiting their confirmation, never that it was added to the calendar."""
    cfg = _configurable(config)
    step_callback = cfg.get("step_callback")
    create_calendar_draft_fn = cfg.get("create_calendar_draft_fn")
    if create_calendar_draft_fn is None:
        return "Cannot draft a calendar event: no draft store available in this context."

    def emit(msg: str) -> None:
        if step_callback:
            step_callback(f"[calendar] {msg}")

    emit("Parsing scheduling request...")
    try:
        event_plan = asyncio.run(parse_schedule_intent(schedule_request))
    except ValueError as e:
        emit(f"FAILED to parse: {e}")
        return f"Could not draft the event: {e}"

    draft = create_calendar_draft_fn(event_plan)
    emit(describe_event_ready(draft.title, draft.start, draft.draft_id))
    return (
        f"Drafted a calendar event '{draft.title}' at {draft.start}, "
        f"draft_id={draft.draft_id}. It has NOT been created yet — it is waiting for "
        "the user to review and click Confirm in the UI."
    )
