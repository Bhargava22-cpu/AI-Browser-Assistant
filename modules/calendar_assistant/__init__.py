from .calendar_client import create_event
from .models import EventPlan, EventResult
from .nl_parser import parse_schedule_intent

__all__ = [
    "create_event",
    "parse_schedule_intent",
    "EventPlan",
    "EventResult",
    "describe_event_ready",
]


def describe_event_ready(title: str, start: str, draft_id: str) -> str:
    """The "draft ready" progress-step message. Exact format is depended on by
    week6/ui/src/components/ActivityLog.jsx's parseCalendarStep regex, which renders
    it as the interactive Confirm/Discard event card — do not change the shape
    without updating that regex too.
    """
    return f"Draft ready — {title} at {start} (draft_id={draft_id})"
