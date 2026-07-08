from .composer import compose_email
from .gmail_client import send_email
from .models import EmailDraftPlan, EmailSendResult

__all__ = [
    "compose_email",
    "send_email",
    "EmailDraftPlan",
    "EmailSendResult",
    "describe_draft_ready",
]


def describe_draft_ready(to_email: str, subject: str, draft_id: str) -> str:
    """The "draft ready" progress-step message. Exact format is depended on by
    week6/ui/src/components/ActivityLog.jsx's parseEmailStep regex, which renders
    it as the interactive Send/Discard draft card — do not change the shape
    without updating that regex too.
    """
    return f"Draft ready — to: {to_email} | subject: {subject} (draft_id={draft_id})"
