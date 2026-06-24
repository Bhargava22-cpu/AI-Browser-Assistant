import asyncio
import sys
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage

import database

# Allow imports from week4/agent/ (tools.py, executor.py live there)
WEEK4_AGENT_DIR = Path(__file__).parent.parent / "week4" / "agent"
if str(WEEK4_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK4_AGENT_DIR))

from executor import build_agent  # noqa: E402 — must come after sys.path fix

# Shared state: one queue per running task, used by background task + WebSocket handler
task_queues: dict[str, asyncio.Queue] = {}

# Agent singleton — expensive to build, safe to reuse across requests
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


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

    def _blocking_run() -> None:
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

    try:
        await loop.run_in_executor(None, _blocking_run)
        await database.update_task_status(task_id, "completed")
    except Exception as e:
        await database.update_task_status(task_id, "failed", error=str(e))
        step_callback(f"[ERROR] {e}")
    finally:
        # Sentinel signals the WebSocket handler to close
        if queue is not None:
            loop.call_soon_threadsafe(queue.put_nowait, None)
