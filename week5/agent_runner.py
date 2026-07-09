import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from groq import APIError
from langchain_core.messages import HumanMessage

import database
from models import CalendarEventDraft, EmailDraft

# Allow imports from week4/agent/ (tools.py, executor.py live there)
WEEK4_AGENT_DIR = Path(__file__).parent.parent / "week4" / "agent"
if str(WEEK4_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK4_AGENT_DIR))

# Allow imports from week3/scripts/ (intent_parser.py)
WEEK3_SCRIPTS_DIR = Path(__file__).parent.parent / "week3" / "scripts"
if str(WEEK3_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK3_SCRIPTS_DIR))

# Allow imports from the repo-root modules/ package (modules/form_filling)
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executor import build_agent  # noqa: E402 — must come after sys.path fix
from intent_parser import parse_intent  # noqa: E402
from tools import get_worker  # noqa: E402

from modules.form_filling import (  # noqa: E402
    answer_missing_fields,
    describe_fill_result,
    describe_missing_field,
    fill_form,
)
from modules.email_assistant import (  # noqa: E402
    EmailDraftPlan,
    compose_email,
    describe_draft_ready,
    send_email,
)
from modules.calendar_assistant import (  # noqa: E402
    EventPlan,
    create_event,
    describe_event_ready,
    parse_schedule_intent,
)

# Shared state: one queue per running task, used by background task + WebSocket handler
task_queues: dict[str, asyncio.Queue] = {}

# In-memory only, keyed by task_id — a fill_form run's still-missing fields, kept
# around so a chat-style reply can answer them on the SAME live page. Tied to the
# live BrowserWorker page (via each FieldSpec's Frame reference), so this doesn't
# need to (and can't meaningfully) survive a server restart either.
_pending_field_prompts: dict[str, list] = {}

# Agent singleton — expensive to build, safe to reuse across requests
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def _profile_to_dict(profile: database.UserProfile) -> dict:
    return {
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "address": json.loads(profile.address),
        "college": profile.college,
        "degree": profile.degree,
        "graduation_year": profile.graduation_year,
        "skills": json.loads(profile.skills),
        "resume_path": profile.resume_path,
        "linkedin": profile.linkedin,
        "github": profile.github,
        "learned_fields": json.loads(profile.learned_fields),
    }


def create_task_queue(task_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    task_queues[task_id] = q
    return q


def get_task_queue(task_id: str) -> Optional[asyncio.Queue]:
    return task_queues.get(task_id)


def remove_task_queue(task_id: str) -> None:
    task_queues.pop(task_id, None)


async def run_agent_task(task_id: str, command: str) -> None:
    await database.update_task_status(task_id, "running")

    loop = asyncio.get_running_loop()
    queue = task_queues.get(task_id)

    def step_callback(step_text: str) -> None:
        # Persist to DB regardless of whether a WebSocket client is connected
        asyncio.run_coroutine_threadsafe(database.append_task_step(task_id, step_text), loop)
        if queue is not None:
            loop.call_soon_threadsafe(queue.put_nowait, step_text)

    draft_created = False

    def _bridge_and_mark_created(coro):
        # Called from the agent's worker thread (via compose_email_draft_tool /
        # create_calendar_draft_tool) — bridge a DB-write coroutine back to the main
        # event loop, same pattern as step_callback's DB bridge above, but blocking
        # since callers need the created row (for its id) back.
        nonlocal draft_created
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        result = future.result()
        draft_created = True
        return result

    def _create_draft_fn(to_email: str, subject: str, body: str) -> EmailDraft:
        return _bridge_and_mark_created(database.create_email_draft(task_id, to_email, subject, body))

    def _create_calendar_draft_fn(event_plan: EventPlan) -> CalendarEventDraft:
        return _bridge_and_mark_created(
            database.create_calendar_draft(
                task_id,
                event_plan.title,
                event_plan.start,
                event_plan.end,
                event_plan.timezone,
                event_plan.recurrence,
                event_plan.attendees,
                event_plan.description,
            )
        )

    def _blocking_run_general(profile: Optional[dict]) -> None:
        agent = get_agent()
        config = {
            "configurable": {
                "thread_id": task_id,
                "profile": profile,
                "step_callback": step_callback,
                "create_draft_fn": _create_draft_fn,
                "create_calendar_draft_fn": _create_calendar_draft_fn,
            }
        }
        for chunk in agent.stream(
            {"messages": [HumanMessage(content=command)]},
            config=config,
            stream_mode="updates",
        ):
            for node_name, node_output in chunk.items():
                if not isinstance(node_output, dict):
                    continue
                messages = node_output.get("messages", [])
                for msg in messages:
                    content = getattr(msg, "content", "")
                    if content:
                        step_callback(f"[{node_name}] {content}")

    def _blocking_run_fill_form(profile: dict, target_url: Optional[str]):
        step_callback("[form_filling] Detecting fields and mapping to profile...")
        result = fill_form(get_worker(), profile, task_id, url=target_url)

        for line in describe_fill_result(result):
            step_callback(f"[form_filling] {line}")

        for warning in result.warnings:
            step_callback(f"[form_filling][warning] {warning}")

        return result

    async def _run_email(profile: dict, intent_data: dict) -> None:
        # Unlike fill_form/general (Playwright/LangChain — genuinely blocking, need
        # run_in_executor), compose_email is pure LLM I/O via AsyncGroq, so this stays
        # on the event loop directly — no thread hop, no cross-thread DB bridging.
        to_email = intent_data.get("recipient", "")
        body_intent = intent_data.get("body_intent", "")
        subject_hint = intent_data.get("subject")

        step_callback(f"[email] Composing message to {to_email}...")
        draft_plan = await compose_email(profile, to_email, body_intent, subject_hint)
        draft = await database.create_email_draft(
            task_id, draft_plan.to_email, draft_plan.subject, draft_plan.body
        )

        step_callback(f"[email] {describe_draft_ready(draft.to_email, draft.subject, draft.draft_id)}")

    async def _run_calendar(schedule_request: str) -> None:
        # Same reasoning as _run_email: parsing is pure LLM I/O (AsyncGroq), no
        # blocking browser work, so it stays directly on the event loop.
        step_callback("[calendar] Parsing scheduling request...")
        event_plan = await parse_schedule_intent(schedule_request)
        draft = await database.create_calendar_draft(
            task_id,
            event_plan.title,
            event_plan.start,
            event_plan.end,
            event_plan.timezone,
            event_plan.recurrence,
            event_plan.attendees,
            event_plan.description,
        )
        step_callback(f"[calendar] {describe_event_ready(draft.title, draft.start, draft.draft_id)}")

    intent: Optional[dict] = None
    try:
        intent = await parse_intent(command)
    except (ValueError, EnvironmentError, APIError) as e:
        step_callback(f"[intent-parser] {e} — falling back to general agent")

    async def _get_profile() -> Optional[dict]:
        profile_row = await database.get_user_profile()
        return _profile_to_dict(profile_row) if profile_row else None

    try:
        if intent and intent.get("action") == "fill_form":
            profile = await _get_profile()
            if profile is None:
                raise ValueError("No user profile found in memory — cannot fill form")
            result = await loop.run_in_executor(
                None, _blocking_run_fill_form, profile, intent.get("target_url")
            )
            if result.missing_fields:
                _pending_field_prompts[task_id] = result.missing_fields
                missing_labels = ", ".join(describe_missing_field(f) for f in result.missing_fields)
                step_callback(
                    f"[form_filling][ask] I need answers for: {missing_labels}. "
                    "Reply below and I'll fill them in and remember them for next time."
                )
                await database.update_task_status(task_id, "awaiting_input")
            else:
                await database.update_task_status(task_id, "completed")
        elif intent and intent.get("action") == "email":
            profile = await _get_profile()
            if profile is None:
                raise ValueError("No user profile found in memory — cannot compose email")
            await _run_email(profile, intent.get("data") or {})
            # Never sent yet — the draft waits for an explicit Send/Discard from the user.
            await database.update_task_status(task_id, "awaiting_confirmation")
        elif intent and intent.get("action") == "calendar":
            # No profile needed — scheduling only reasons about the request text/dates.
            schedule_request = (intent.get("data") or {}).get("schedule_request") or command
            await _run_calendar(schedule_request)
            # Never created yet — the draft waits for an explicit Confirm/Discard from the user.
            await database.update_task_status(task_id, "awaiting_confirmation")
        else:
            # Falls through to the general ReAct agent, which also has fill_form_tool
            # and compose_email_draft_tool available — this is the path that lets a
            # compound/cross-module command chain them (Module 5).
            profile = await _get_profile()
            await loop.run_in_executor(None, _blocking_run_general, profile)
            # If the agent drafted an email along the way, the task must stay open for
            # the user's Send/Discard decision rather than reporting "completed".
            status = "awaiting_confirmation" if draft_created else "completed"
            await database.update_task_status(task_id, status)
    except Exception as e:
        await database.update_task_status(task_id, "failed", error=str(e))
        step_callback(f"[ERROR] {e}")
    finally:
        # Sentinel signals the WebSocket handler to close
        if queue is not None:
            loop.call_soon_threadsafe(queue.put_nowait, None)


async def _fetch_pending_draft(get_fn, draft_id: str):
    """Shared fetch+guard prologue for any draft-like row (email/calendar draft):
    fetch by id, then report whether it's still awaiting the user's decision.
    Callers that only care about the binary "resolved vs. still pending" case can
    return `draft` directly once `is_pending` is False — that's the idempotent
    no-op every action route below needs (don't double-send/double-create/etc.)."""
    draft = await get_fn(draft_id)
    if draft is None:
        return None, False
    return draft, draft.status == "pending_confirmation"


async def confirm_email_send(draft_id: str) -> Optional[EmailDraft]:
    """Actually invokes the Gmail API — only ever called from the explicit
    POST /email/drafts/{id}/send route, never automatically."""
    draft, is_pending = await _fetch_pending_draft(database.get_email_draft, draft_id)
    if draft is None or not is_pending:
        return draft  # not found, or already resolved — idempotent no-op, blocks double-send

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        send_email,
        EmailDraftPlan(to_email=draft.to_email, subject=draft.subject, body=draft.body),
    )

    if result.success:
        updated = await database.update_email_draft_status(
            draft_id, "sent", sent_at=datetime.now(timezone.utc)
        )
        await database.append_task_step(draft.task_id, f"[email] sent to {draft.to_email}")
        await database.update_task_status(draft.task_id, "completed")
    else:
        updated = await database.update_email_draft_status(draft_id, "failed", error=result.error)
        await database.append_task_step(draft.task_id, f"[email] send FAILED ({result.error})")
        await database.update_task_status(draft.task_id, "failed", error=result.error)

    return updated


async def revise_email_draft(draft_id: str, feedback: str) -> Optional[EmailDraft]:
    """Re-composes a still-pending draft's subject/body in place based on user
    feedback — only ever called from the explicit POST /email/drafts/{id}/revise
    route. Leaves status as pending_confirmation; the user still must explicitly
    Send or Discard afterward."""
    draft, is_pending = await _fetch_pending_draft(database.get_email_draft, draft_id)
    if draft is None or not is_pending:
        return draft  # not found, or already resolved — nothing left to revise

    profile_row = await database.get_user_profile()
    if profile_row is None:
        raise ValueError("No user profile found in memory — cannot revise email")
    profile = _profile_to_dict(profile_row)

    revised = await compose_email(
        profile,
        draft.to_email,
        "",
        revise_from=EmailDraftPlan(to_email=draft.to_email, subject=draft.subject, body=draft.body),
        feedback=feedback,
    )
    updated = await database.update_email_draft_content(draft_id, revised.subject, revised.body)
    await database.append_task_step(draft.task_id, "[email] draft revised per user feedback")
    return updated


async def _discard_draft(get_fn, update_status_fn, log_tag: str, draft_id: str):
    """Shared discard flow for any draft type (email, calendar, ...): fetch, guard
    against re-resolving an already-decided draft, mark discarded, and log it."""
    draft, is_pending = await _fetch_pending_draft(get_fn, draft_id)
    if draft is None or not is_pending:
        return draft  # not found, or already resolved — idempotent no-op

    updated = await update_status_fn(draft_id, "discarded")
    await database.append_task_step(draft.task_id, f"[{log_tag}] discarded by user")
    await database.update_task_status(draft.task_id, "completed")
    return updated


async def discard_email_draft(draft_id: str) -> Optional[EmailDraft]:
    return await _discard_draft(database.get_email_draft, database.update_email_draft_status, "email", draft_id)


async def confirm_calendar_event(draft_id: str) -> Optional[CalendarEventDraft]:
    """Actually invokes the Google Calendar API — only ever called from the explicit
    POST /calendar/drafts/{id}/confirm route, never automatically."""
    draft, is_pending = await _fetch_pending_draft(database.get_calendar_draft, draft_id)
    if draft is None or not is_pending:
        return draft  # not found, or already resolved — idempotent no-op, blocks double-create

    loop = asyncio.get_running_loop()
    event_plan = EventPlan(
        title=draft.title,
        start=draft.start,
        end=draft.end,
        timezone=draft.timezone,
        recurrence=draft.recurrence,
        attendees=json.loads(draft.attendees),
        description=draft.description,
    )
    result = await loop.run_in_executor(None, create_event, event_plan)

    if result.success:
        updated = await database.update_calendar_draft_status(
            draft_id,
            "created",
            event_id=result.event_id,
            html_link=result.html_link,
            confirmed_at=datetime.now(timezone.utc),
        )
        await database.append_task_step(
            draft.task_id, f"[calendar] created: {draft.title} (event_id={result.event_id})"
        )
        await database.update_task_status(draft.task_id, "completed")
    else:
        updated = await database.update_calendar_draft_status(draft_id, "failed", error=result.error)
        await database.append_task_step(draft.task_id, f"[calendar] create FAILED ({result.error})")
        await database.update_task_status(draft.task_id, "failed", error=result.error)

    return updated


async def discard_calendar_draft(draft_id: str) -> Optional[CalendarEventDraft]:
    return await _discard_draft(
        database.get_calendar_draft, database.update_calendar_draft_status, "calendar", draft_id
    )


async def answer_task_reply(task_id: str, message: str) -> dict:
    """Handles a chat-style reply to a task awaiting input (currently only
    form_filling's missing-field prompts): matches the reply against the fields
    that task is still missing, fills whatever it answers on the still-open live
    page, persists those answers as learned_fields for future forms, and reports
    back what happened. Only ever called from the explicit POST /tasks/{id}/reply
    route.

    Unlike the email/calendar draft flows, there's no DB-backed queue to fetch —
    the pending fields only exist in _pending_field_prompts, tied to the live
    BrowserWorker page from the original fill_form() run.
    """
    missing = _pending_field_prompts.get(task_id)
    if not missing:
        raise ValueError("This task has no pending questions to reply to")

    loop = asyncio.get_running_loop()
    outcomes, still_missing, learned = await loop.run_in_executor(
        None, answer_missing_fields, get_worker(), missing, message
    )

    for outcome in outcomes:
        status_text = "filled" if outcome.success else f"FAILED ({outcome.error})"
        label = outcome.field.label or outcome.field.selector
        await database.append_task_step(task_id, f"[form_filling] {label}: {status_text}")

    if learned:
        await database.save_learned_fields(learned)

    if still_missing:
        _pending_field_prompts[task_id] = still_missing
        new_status = "awaiting_input"
    else:
        _pending_field_prompts.pop(task_id, None)
        await database.append_task_step(task_id, "[form_filling] all questions answered")
        new_status = "completed"
    await database.update_task_status(task_id, new_status)

    return {
        "filled": [
            {"label": o.field.label or o.field.selector, "success": o.success, "error": o.error}
            for o in outcomes
        ],
        "still_missing": [describe_missing_field(f) for f in still_missing],
        "status": new_status,
    }
