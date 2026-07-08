import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine, select

from models import EmailDraft, Task, UserProfile

# Allow importing the repo-root modules/ package (modules/form_filling), same as
# week5/agent_runner.py — needed for the shared learned-field label normalizer.
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.form_filling import normalize_label  # noqa: E402

WEEK1_PROFILE_PATH = Path(__file__).parent.parent / "week1" / "data" / "user_profile.json"
DB_PATH = Path(__file__).parent / "agent.db"

SYNC_URL = f"sqlite:///{DB_PATH}"
ASYNC_URL = f"sqlite+aiosqlite:///{DB_PATH}"

sync_engine = create_engine(SYNC_URL, echo=False)
async_engine = create_async_engine(ASYNC_URL, echo=False)

async_session_factory = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_session():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    SQLModel.metadata.create_all(sync_engine)
    _ensure_learned_fields_column()


def _ensure_learned_fields_column() -> None:
    """SQLModel.metadata.create_all() only creates missing tables, it never alters
    existing ones — so a pre-existing agent.db from before this column was added
    needs a one-time, idempotent migration."""
    with sync_engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(userprofile)")}
        if columns and "learned_fields" not in columns:
            conn.exec_driver_sql("ALTER TABLE userprofile ADD COLUMN learned_fields VARCHAR DEFAULT '{}'")
            conn.commit()


async def seed_profile_from_json():
    async with get_session() as session:
        result = await session.execute(select(UserProfile).where(UserProfile.id == 1))
        existing = result.scalar_one_or_none()
        if existing:
            return

    if not WEEK1_PROFILE_PATH.exists():
        return

    with open(WEEK1_PROFILE_PATH) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in profile seed file: {e}") from e

    async with get_session() as session:
        profile = UserProfile(
            id=1,
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            address=json.dumps(data.get("address", {})),
            college=data.get("college", ""),
            degree=data.get("degree", ""),
            graduation_year=data.get("graduation_year", 0),
            skills=json.dumps(data.get("skills", [])),
            resume_path=data.get("resume_path", ""),
            linkedin=data.get("linkedin", ""),
            github=data.get("github", ""),
        )
        session.add(profile)


# ---------- Task CRUD ----------

async def create_task(command: str) -> Task:
    async with get_session() as session:
        task = Task(command=command)
        session.add(task)
        await session.flush()
        await session.refresh(task)
        return task


async def get_task(task_id: str) -> Optional[Task]:
    async with get_session() as session:
        result = await session.execute(select(Task).where(Task.task_id == task_id))
        return result.scalar_one_or_none()


async def update_task_status(task_id: str, status: str, error: Optional[str] = None) -> None:
    async with get_session() as session:
        result = await session.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.status = status
            if error:
                task.error = error
            session.add(task)


async def append_task_step(task_id: str, step: str) -> None:
    async with get_session() as session:
        result = await session.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()
        if task:
            steps = json.loads(task.steps)
            steps.append(step)
            task.steps = json.dumps(steps)
            session.add(task)


# ---------- UserProfile CRUD ----------

async def get_user_profile() -> Optional[UserProfile]:
    async with get_session() as session:
        result = await session.execute(select(UserProfile).where(UserProfile.id == 1))
        return result.scalar_one_or_none()


async def upsert_user_profile(data: dict) -> UserProfile:
    address = data.get("address", {})
    skills = data.get("skills", [])

    async with get_session() as session:
        result = await session.execute(select(UserProfile).where(UserProfile.id == 1))
        profile = result.scalar_one_or_none()

        if profile is None:
            profile = UserProfile(id=1)

        profile.name = data.get("name", "")
        profile.email = data.get("email", "")
        profile.phone = data.get("phone", "")
        profile.address = json.dumps(address if isinstance(address, dict) else address.model_dump())
        profile.college = data.get("college", "")
        profile.degree = data.get("degree", "")
        profile.graduation_year = data.get("graduation_year", 0)
        profile.skills = json.dumps(skills)
        profile.resume_path = data.get("resume_path", "")
        profile.linkedin = data.get("linkedin", "")
        profile.github = data.get("github", "")

        session.add(profile)
        await session.flush()
        await session.refresh(profile)
        return profile


# ---------- Learned fields (answers to previously-missing form fields) ----------

async def get_learned_fields() -> dict:
    profile = await get_user_profile()
    if profile is None:
        return {}
    return json.loads(profile.learned_fields)


async def save_learned_fields(answers: dict) -> dict:
    async with get_session() as session:
        result = await session.execute(select(UserProfile).where(UserProfile.id == 1))
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError("No user profile found — cannot save learned fields")

        learned = json.loads(profile.learned_fields)
        learned.update({normalize_label(k): v for k, v in answers.items()})
        profile.learned_fields = json.dumps(learned)

        session.add(profile)
        await session.flush()
        await session.refresh(profile)
        return json.loads(profile.learned_fields)


# ---------- EmailDraft CRUD (Module 2 — draft/confirm/send flow) ----------

async def create_email_draft(task_id: str, to_email: str, subject: str, body: str) -> EmailDraft:
    async with get_session() as session:
        draft = EmailDraft(task_id=task_id, to_email=to_email, subject=subject, body=body)
        session.add(draft)
        await session.flush()
        await session.refresh(draft)
        return draft


async def get_email_draft(draft_id: str) -> Optional[EmailDraft]:
    async with get_session() as session:
        result = await session.execute(select(EmailDraft).where(EmailDraft.draft_id == draft_id))
        return result.scalar_one_or_none()


async def update_email_draft_status(
    draft_id: str,
    status: str,
    error: Optional[str] = None,
    sent_at: Optional[datetime] = None,
) -> Optional[EmailDraft]:
    async with get_session() as session:
        result = await session.execute(select(EmailDraft).where(EmailDraft.draft_id == draft_id))
        draft = result.scalar_one_or_none()
        if draft:
            draft.status = status
            if error is not None:
                draft.error = error
            if sent_at is not None:
                draft.sent_at = sent_at
            session.add(draft)
            await session.flush()
            await session.refresh(draft)
        return draft
