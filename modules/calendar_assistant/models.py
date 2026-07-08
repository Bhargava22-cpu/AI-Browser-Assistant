from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EventPlan:
    title: str
    start: str  # ISO 8601 datetime, e.g. "2026-07-09T20:00:00+05:30"
    end: str  # ISO 8601 datetime
    timezone: str  # IANA tz name, e.g. "Asia/Kolkata"
    recurrence: Optional[str] = None  # RFC5545 RRULE, e.g. "RRULE:FREQ=DAILY;COUNT=14"
    attendees: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class EventResult:
    success: bool
    event_id: Optional[str] = None
    html_link: Optional[str] = None
    error: Optional[str] = None
