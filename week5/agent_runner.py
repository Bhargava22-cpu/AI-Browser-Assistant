import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from groq import APIError
from langchain_core.messages import HumanMessage

import database
from models import EmailDraft

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

from modules.form_filling import fill_form  # noqa: E402
from modules.email_assistant import EmailDraftPlan, compose_email, send_email  # noqa: E402

# Shared state: one queue per running task, used by background task + WebSocket handler
task_queues: dict[str, asyncio.Queue] = {}

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

    def _blocking_run_general() -> None:
        agent = get_agent()
        config = {"configurable": {"thread_id": task_id}}
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

    def _blocking_run_fill_form(profile: dict, target_url: Optional[str]) -> None:
        step_callback("[form_filling] Detecting fields and mapping to profile...")
        result = fill_form(get_worker(), profile, task_id, url=target_url)

        for outcome in result.filled_fields:
            status = "filled" if outcome.success else f"FAILED ({outcome.error})"
            label = outcome.field.label or outcome.field.selector
            step_callback(f"[form_filling] {label}: {status}")

        if result.upload and result.upload.attempted:
            upload_status = "uploaded" if result.upload.success else f"FAILED ({result.upload.error})"
            step_callback(f"[form_filling] resume upload: {upload_status}")

        if result.missing_fields:
            missing_labels = ", ".join(f.label or f.selector for f in result.missing_fields)
            step_callback(
                f"[form_filling] needs manual input: {missing_labels} — "
                "answer once via POST /user/learned-fields (key = exact field label) "
                "and it will be filled automatically on future forms"
            )

        for warning in result.warnings:
            step_callback(f"[form_filling][warning] {warning}")

        preview_note = (
            f" (screenshot: {result.preview.screenshot_path})" if result.preview.screenshot_path else ""
        )
        step_callback(f"[form_filling] Preview ready — review before submitting{preview_note}")

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

        step_callback(
            f"[email] Draft ready — to: {draft.to_email} | subject: {draft.subject} "
            f"(draft_id={draft.draft_id})"
        )

    intent: Optional[dict] = None
    try:
        intent = await parse_intent(command)
    except (ValueError, EnvironmentError, APIError) as e:
        step_callback(f"[intent-parser] {e} — falling back to general agent")

    try:
        if intent and intent.get("action") == "fill_form":
            profile_row = await database.get_user_profile()
            if profile_row is None:
                raise ValueError("No user profile found in memory — cannot fill form")
            profile = _profile_to_dict(profile_row)
            await loop.run_in_executor(
                None, _blocking_run_fill_form, profile, intent.get("target_url")
            )
            await database.update_task_status(task_id, "completed")
        elif intent and intent.get("action") == "email":
            profile_row = await database.get_user_profile()
            if profile_row is None:
                raise ValueError("No user profile found in memory — cannot compose email")
            profile = _profile_to_dict(profile_row)
            await _run_email(profile, intent.get("data") or {})
            # Never sent yet — the draft waits for an explicit Send/Discard from the user.
            await database.update_task_status(task_id, "awaiting_confirmation")
        else:
            await loop.run_in_executor(None, _blocking_run_general)
            await database.update_task_status(task_id, "completed")
    except Exception as e:
        await database.update_task_status(task_id, "failed", error=str(e))
        step_callback(f"[ERROR] {e}")
    finally:
        # Sentinel signals the WebSocket handler to close
        if queue is not None:
            loop.call_soon_threadsafe(queue.put_nowait, None)


async def confirm_email_send(draft_id: str) -> Optional[EmailDraft]:
    """Actually invokes the Gmail API — only ever called from the explicit
    POST /email/drafts/{id}/send route, never automatically."""
    draft = await database.get_email_draft(draft_id)
    if draft is None:
        return None
    if draft.status != "pending_confirmation":
        return draft  # already resolved — idempotent no-op, blocks double-send

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


async def discard_email_draft(draft_id: str) -> Optional[EmailDraft]:
    draft = await database.get_email_draft(draft_id)
    if draft is None:
        return None
    if draft.status != "pending_confirmation":
        return draft  # already resolved — idempotent no-op

    updated = await database.update_email_draft_status(draft_id, "discarded")
    await database.append_task_step(draft.task_id, "[email] discarded by user")
    await database.update_task_status(draft.task_id, "completed")
    return updated
