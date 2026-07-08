import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from groq import APIError

from modules.calendar_assistant.models import EventPlan
from modules.calendar_assistant.nl_parser import parse_schedule_intent

_NOW = datetime(2026, 7, 9, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def run(coro):
    return asyncio.run(coro)


def _mock_llm_response(payload: dict) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = json.dumps(payload)
    mock_result = MagicMock()
    mock_result.choices = [MagicMock(message=mock_message)]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)
    return mock_client


def test_empty_command_raises_without_calling_llm():
    with patch("modules.calendar_assistant.nl_parser._client_instance") as mock_instance:
        with pytest.raises(ValueError, match="scheduling request is required"):
            run(parse_schedule_intent(""))

    mock_instance.assert_not_called()


def test_recurring_event_parses_into_event_plan():
    mock_client = _mock_llm_response(
        {
            "title": "DSA practice",
            "start": "2026-07-09T20:00:00+05:30",
            "end": "2026-07-09T21:00:00+05:30",
            "recurrence": "RRULE:FREQ=DAILY;COUNT=14",
            "attendees": [],
            "description": "",
        }
    )
    with patch("modules.calendar_assistant.nl_parser._client_instance", return_value=mock_client):
        plan = run(
            parse_schedule_intent(
                "add DSA practice every day at 8pm for 2 weeks", now=_NOW, tz_name="Asia/Kolkata"
            )
        )

    assert plan == EventPlan(
        title="DSA practice",
        start="2026-07-09T20:00:00+05:30",
        end="2026-07-09T21:00:00+05:30",
        timezone="Asia/Kolkata",
        recurrence="RRULE:FREQ=DAILY;COUNT=14",
        attendees=[],
        description="",
    )


def test_one_off_event_has_no_recurrence():
    mock_client = _mock_llm_response(
        {
            "title": "Call with mentor",
            "start": "2026-07-10T15:00:00+05:30",
            "end": "2026-07-10T15:30:00+05:30",
            "recurrence": None,
            "attendees": ["mentor@example.com"],
            "description": "",
        }
    )
    with patch("modules.calendar_assistant.nl_parser._client_instance", return_value=mock_client):
        plan = run(
            parse_schedule_intent("call with mentor tomorrow at 3pm", now=_NOW, tz_name="Asia/Kolkata")
        )

    assert plan.recurrence is None
    assert plan.attendees == ["mentor@example.com"]


def test_non_string_attendees_are_dropped():
    mock_client = _mock_llm_response(
        {
            "title": "Standup",
            "start": "2026-07-10T09:00:00+05:30",
            "end": "2026-07-10T09:15:00+05:30",
            "recurrence": None,
            "attendees": ["ok@example.com", 42, None],
            "description": "",
        }
    )
    with patch("modules.calendar_assistant.nl_parser._client_instance", return_value=mock_client):
        plan = run(parse_schedule_intent("standup tomorrow at 9am", now=_NOW, tz_name="Asia/Kolkata"))

    assert plan.attendees == ["ok@example.com"]


def test_missing_required_fields_raises():
    mock_client = _mock_llm_response({"title": "Standup", "recurrence": None})
    with patch("modules.calendar_assistant.nl_parser._client_instance", return_value=mock_client):
        with pytest.raises(ValueError, match="did not return a complete event"):
            run(parse_schedule_intent("standup tomorrow", now=_NOW, tz_name="Asia/Kolkata"))


def test_groq_api_error_bubbles_as_value_error():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIError("boom", request=MagicMock(), body=None)
    )
    with patch("modules.calendar_assistant.nl_parser._client_instance", return_value=mock_client):
        with pytest.raises(ValueError, match="Failed to parse scheduling request"):
            run(parse_schedule_intent("standup tomorrow", now=_NOW, tz_name="Asia/Kolkata"))


def test_malformed_json_response_bubbles_as_value_error():
    mock_message = MagicMock()
    mock_message.content = "not json at all"
    mock_result = MagicMock()
    mock_result.choices = [MagicMock(message=mock_message)]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)

    with patch("modules.calendar_assistant.nl_parser._client_instance", return_value=mock_client):
        with pytest.raises(ValueError, match="Failed to parse scheduling request"):
            run(parse_schedule_intent("standup tomorrow", now=_NOW, tz_name="Asia/Kolkata"))


def test_defaults_are_used_when_now_and_tz_not_supplied():
    mock_client = _mock_llm_response(
        {
            "title": "Standup",
            "start": "2026-07-10T09:00:00+05:30",
            "end": "2026-07-10T09:15:00+05:30",
            "recurrence": None,
            "attendees": [],
            "description": "",
        }
    )
    with patch("modules.calendar_assistant.nl_parser._client_instance", return_value=mock_client):
        plan = run(parse_schedule_intent("standup tomorrow at 9am"))

    assert plan.timezone  # falls back to DEFAULT_TIMEZONE, not empty
