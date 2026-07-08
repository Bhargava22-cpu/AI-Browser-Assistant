import json
import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from groq import APIError

from ._llm import get_groq_client as _client_instance
from ._llm import get_text_model, parse_json_response
from .models import EventPlan

# No timezone field exists on the user profile yet — a single configurable default
# is enough for V1 rather than plumbing timezone through the profile schema.
DEFAULT_TIMEZONE = os.getenv("AGENT_TIMEZONE", "Asia/Kolkata")

_SCHEDULE_SYSTEM_PROMPT = """You convert a natural language scheduling request into a
structured calendar event plan.

You are given the current date/time and timezone as context, and the user's request.
Resolve all relative dates ("tomorrow", "this week", "next Monday") against that
current date/time. Always output concrete ISO 8601 datetimes carrying the given
timezone's UTC offset, never relative phrases. If no duration is implied, default
to a 1 hour event.

For recurring requests (e.g. "every day for 2 weeks", "every Monday for a month"),
output an RFC5545 RRULE string in the "recurrence" field (e.g.
"RRULE:FREQ=DAILY;COUNT=14" or "RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=4"). For a
one-off event, set "recurrence" to null.

If the request names people to invite by email address, include them in
"attendees". Do not invent attendees that weren't mentioned, and do not resolve
a name (e.g. "my mentor") to a guessed email address — leave attendees empty
for those instead.

Output ONLY a JSON object with keys: "title", "start", "end", "recurrence",
"attendees" (list of email strings), "description". No markdown, no explanation.

Example:
User request: "add DSA practice every day at 8pm for 2 weeks"
Current datetime: 2026-07-09T10:00:00+05:30, timezone Asia/Kolkata
Output: {"title": "DSA practice", "start": "2026-07-09T20:00:00+05:30", "end": "2026-07-09T21:00:00+05:30", "recurrence": "RRULE:FREQ=DAILY;COUNT=14", "attendees": [], "description": ""}
"""


async def parse_schedule_intent(
    command_text: str,
    now: Optional[datetime] = None,
    tz_name: Optional[str] = None,
) -> EventPlan:
    if not command_text:
        raise ValueError("A scheduling request is required")

    tz_name = tz_name or DEFAULT_TIMEZONE
    now = now or datetime.now(ZoneInfo(tz_name))

    user_prompt = json.dumps(
        {
            "request": command_text,
            "current_datetime": now.isoformat(),
            "timezone": tz_name,
        }
    )

    try:
        response = await _client_instance().chat.completions.create(
            model=get_text_model(),
            messages=[
                {"role": "system", "content": _SCHEDULE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        parsed = parse_json_response(response.choices[0].message.content)
    except (APIError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to parse scheduling request: {e}") from e

    title = parsed.get("title")
    start = parsed.get("start")
    end = parsed.get("end")
    if not title or not start or not end:
        raise ValueError("LLM did not return a complete event (title/start/end required)")

    attendees = [a for a in parsed.get("attendees", []) if isinstance(a, str)]

    return EventPlan(
        title=title,
        start=start,
        end=end,
        timezone=tz_name,
        recurrence=parsed.get("recurrence") or None,
        attendees=attendees,
        description=parsed.get("description") or "",
    )
