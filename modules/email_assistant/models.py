from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailDraftPlan:
    to_email: str
    subject: str
    body: str


@dataclass
class EmailSendResult:
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
