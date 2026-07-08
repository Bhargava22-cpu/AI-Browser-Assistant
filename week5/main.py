import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import agent_runner
import database
from models import (
    CommandRequest,
    CommandResponse,
    EmailDraftResponse,
    LearnedFieldsRequest,
    LearnedFieldsResponse,
    TaskResponse,
    UserProfileRequest,
    UserProfileResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    await database.seed_profile_from_json()
    yield


app = FastAPI(title="AI Browser Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "AI Browser Agent API", "version": "0.1.0", "docs": "/docs"}


@app.post("/command", response_model=CommandResponse)
async def post_command(body: CommandRequest, background_tasks: BackgroundTasks):
    task = await database.create_task(body.command)
    # Queue must exist before background task starts to avoid a race with WebSocket clients
    agent_runner.create_task_queue(task.task_id)
    background_tasks.add_task(agent_runner.run_agent_task, task.task_id, body.command)
    return CommandResponse(
        task_id=task.task_id,
        status="pending",
        message=f"Task queued. Connect to /ws/{task.task_id} for live updates.",
    )


@app.get("/status/{task_id}", response_model=TaskResponse)
async def get_status(task_id: str):
    task = await database.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task.model_dump())


@app.get("/user/profile", response_model=UserProfileResponse)
async def get_profile():
    profile = await database.get_user_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return UserProfileResponse.model_validate(profile.model_dump())


@app.post("/user/profile", response_model=UserProfileResponse)
async def update_profile(body: UserProfileRequest):
    profile = await database.upsert_user_profile(body.model_dump())
    return UserProfileResponse.model_validate(profile.model_dump())


@app.get("/user/learned-fields", response_model=LearnedFieldsResponse)
async def get_learned_fields():
    return LearnedFieldsResponse(learned_fields=await database.get_learned_fields())


@app.post("/user/learned-fields", response_model=LearnedFieldsResponse)
async def post_learned_fields(body: LearnedFieldsRequest):
    # Keys should be the exact field label as reported in a task's "needs manual input"
    # step (case/whitespace-insensitive) — modules.form_filling.mapper.normalize_label
    # is the canonical normalizer applied on the matching side.
    try:
        learned = await database.save_learned_fields(body.answers)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return LearnedFieldsResponse(learned_fields=learned)


@app.get("/email/drafts/{draft_id}", response_model=EmailDraftResponse)
async def get_email_draft(draft_id: str):
    draft = await database.get_email_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return EmailDraftResponse.model_validate(draft.model_dump())


@app.post("/email/drafts/{draft_id}/send", response_model=EmailDraftResponse)
async def send_email_draft(draft_id: str):
    # agent_runner.confirm_email_send is the only path that ever calls the Gmail API —
    # this route exists solely so a human click can reach it.
    draft = await agent_runner.confirm_email_send(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return EmailDraftResponse.model_validate(draft.model_dump())


@app.post("/email/drafts/{draft_id}/discard", response_model=EmailDraftResponse)
async def discard_email_draft(draft_id: str):
    draft = await agent_runner.discard_email_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return EmailDraftResponse.model_validate(draft.model_dump())


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()

    task = await database.get_task(task_id)
    if not task:
        await websocket.send_json({"type": "error", "content": "Task not found"})
        await websocket.close()
        return

    queue = agent_runner.get_task_queue(task_id)

    # Task already completed before WebSocket connected — replay from DB
    if queue is None:
        stored = await database.get_task(task_id)
        steps = json.loads(stored.steps) if stored else []
        for step in steps:
            await websocket.send_json({"type": "step", "content": step})
        status = stored.status if stored else "unknown"
        await websocket.send_json({"type": "done", "status": status})
        await websocket.close()
        return

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
                continue

            if item is None:  # sentinel — agent finished
                final_task = await database.get_task(task_id)
                status = final_task.status if final_task else "unknown"
                await websocket.send_json({"type": "done", "status": status})
                agent_runner.remove_task_queue(task_id)
                break

            await websocket.send_json({"type": "step", "content": item})

    except WebSocketDisconnect:
        pass  # client disconnected mid-stream — don't purge queue so reconnect works
