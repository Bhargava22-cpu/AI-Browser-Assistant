import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, model_validator
from sqlmodel import Field, SQLModel


# ---------- SQLModel tables ----------

class Task(SQLModel, table=True):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    command: str
    status: str = Field(default="pending")  # pending | running | awaiting_confirmation | completed | failed
    steps: str = Field(default="[]")        # JSON-serialized list[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = Field(default=None)


class UserProfile(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)  # single-row table
    name: str
    email: str
    phone: str
    address: str        # JSON string {"street", "city", "state", "pincode", "country"}
    college: str
    degree: str
    graduation_year: int
    skills: str         # JSON string list[str]
    resume_path: str
    linkedin: str
    github: str
    learned_fields: str = Field(default="{}")  # JSON string {normalized_label: answer}


class EmailDraft(SQLModel, table=True):
    draft_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: str
    to_email: str
    subject: str
    body: str
    status: str = Field(default="pending_confirmation")  # pending_confirmation | sent | failed | discarded
    error: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = Field(default=None)


class CalendarEventDraft(SQLModel, table=True):
    draft_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: str
    title: str
    start: str  # ISO 8601 datetime string
    end: str  # ISO 8601 datetime string
    timezone: str
    recurrence: Optional[str] = Field(default=None)  # RFC5545 RRULE
    attendees: str = Field(default="[]")  # JSON string list[str]
    description: str = Field(default="")
    status: str = Field(default="pending_confirmation")  # pending_confirmation | created | failed | discarded
    error: Optional[str] = Field(default=None)
    event_id: Optional[str] = Field(default=None)  # Google Calendar event id, once created
    html_link: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: Optional[datetime] = Field(default=None)


# ---------- API request/response models ----------

class CommandRequest(BaseModel):
    command: str


class CommandResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskResponse(BaseModel):
    task_id: str
    command: str
    status: str
    steps: list[str]
    created_at: datetime
    error: Optional[str]

    @model_validator(mode="before")
    @classmethod
    def parse_steps(cls, data):
        if isinstance(data, dict) and isinstance(data.get("steps"), str):
            data["steps"] = json.loads(data["steps"])
        return data


class AddressModel(BaseModel):
    street: str
    city: str
    state: str
    pincode: str
    country: str


class UserProfileRequest(BaseModel):
    name: str
    email: str
    phone: str
    address: AddressModel
    college: str
    degree: str
    graduation_year: int
    skills: list[str]
    resume_path: str
    linkedin: str
    github: str


class UserProfileResponse(BaseModel):
    name: str
    email: str
    phone: str
    address: AddressModel
    college: str
    degree: str
    graduation_year: int
    skills: list[str]
    resume_path: str
    linkedin: str
    github: str

    @model_validator(mode="before")
    @classmethod
    def parse_json_fields(cls, data):
        if isinstance(data, dict):
            if isinstance(data.get("address"), str):
                data["address"] = json.loads(data["address"])
            if isinstance(data.get("skills"), str):
                data["skills"] = json.loads(data["skills"])
        return data


class AgentAction(BaseModel):
    task_id: str
    step_index: int
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LearnedFieldsRequest(BaseModel):
    # normalized_label -> answer, e.g. {"how did you hear about us?": "Referred by a friend"}
    answers: dict[str, str]


class LearnedFieldsResponse(BaseModel):
    learned_fields: dict[str, str]


class EmailDraftResponse(BaseModel):
    draft_id: str
    task_id: str
    to_email: str
    subject: str
    body: str
    status: str
    error: Optional[str]
    created_at: datetime
    sent_at: Optional[datetime]


class EmailDraftReviseRequest(BaseModel):
    feedback: str


class CalendarEventDraftResponse(BaseModel):
    draft_id: str
    task_id: str
    title: str
    start: str
    end: str
    timezone: str
    recurrence: Optional[str]
    attendees: list[str]
    description: str
    status: str
    error: Optional[str]
    event_id: Optional[str]
    html_link: Optional[str]
    created_at: datetime
    confirmed_at: Optional[datetime]

    @model_validator(mode="before")
    @classmethod
    def parse_attendees(cls, data):
        if isinstance(data, dict) and isinstance(data.get("attendees"), str):
            data["attendees"] = json.loads(data["attendees"])
        return data


class TaskReplyRequest(BaseModel):
    message: str


class FilledFieldOutcome(BaseModel):
    label: str
    success: bool
    error: Optional[str] = None


class TaskReplyResponse(BaseModel):
    filled: list[FilledFieldOutcome]
    still_missing: list[str]
    status: str
