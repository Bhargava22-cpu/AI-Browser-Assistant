from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from modules.calendar_assistant import calendar_client
from modules.calendar_assistant.models import EventPlan


@pytest.fixture(autouse=True)
def reset_service_singleton():
    calendar_client._service = None
    yield
    calendar_client._service = None


def _plan(**overrides) -> EventPlan:
    defaults = dict(
        title="DSA practice",
        start="2026-07-09T20:00:00+05:30",
        end="2026-07-09T21:00:00+05:30",
        timezone="Asia/Kolkata",
        recurrence=None,
        attendees=[],
        description="",
    )
    defaults.update(overrides)
    return EventPlan(**defaults)


def test_create_event_success():
    mock_service = MagicMock()
    mock_service.events.return_value.insert.return_value.execute.return_value = {
        "id": "evt123",
        "htmlLink": "https://calendar.google.com/event?eid=abc",
    }

    with patch("modules.calendar_assistant.calendar_client.get_calendar_service", return_value=mock_service):
        result = calendar_client.create_event(_plan())

    assert result.success is True
    assert result.event_id == "evt123"
    assert result.html_link == "https://calendar.google.com/event?eid=abc"
    assert result.error is None


def test_create_event_without_attendees_sends_no_updates():
    mock_service = MagicMock()
    mock_service.events.return_value.insert.return_value.execute.return_value = {"id": "evt123"}

    with patch("modules.calendar_assistant.calendar_client.get_calendar_service", return_value=mock_service):
        calendar_client.create_event(_plan(attendees=[]))

    _, kwargs = mock_service.events.return_value.insert.call_args
    assert kwargs["sendUpdates"] == "none"
    assert "attendees" not in kwargs["body"]


def test_create_event_with_attendees_sends_updates_to_all():
    mock_service = MagicMock()
    mock_service.events.return_value.insert.return_value.execute.return_value = {"id": "evt123"}

    with patch("modules.calendar_assistant.calendar_client.get_calendar_service", return_value=mock_service):
        calendar_client.create_event(_plan(attendees=["mentor@example.com"]))

    _, kwargs = mock_service.events.return_value.insert.call_args
    assert kwargs["sendUpdates"] == "all"
    assert kwargs["body"]["attendees"] == [{"email": "mentor@example.com"}]


def test_create_event_with_recurrence_includes_rrule():
    mock_service = MagicMock()
    mock_service.events.return_value.insert.return_value.execute.return_value = {"id": "evt123"}

    with patch("modules.calendar_assistant.calendar_client.get_calendar_service", return_value=mock_service):
        calendar_client.create_event(_plan(recurrence="RRULE:FREQ=DAILY;COUNT=14"))

    _, kwargs = mock_service.events.return_value.insert.call_args
    assert kwargs["body"]["recurrence"] == ["RRULE:FREQ=DAILY;COUNT=14"]


def test_create_event_http_error_is_caught_not_raised():
    mock_service = MagicMock()
    http_error = HttpError(resp=MagicMock(status=403), content=b'{"error": "forbidden"}')
    mock_service.events.return_value.insert.return_value.execute.side_effect = http_error

    with patch("modules.calendar_assistant.calendar_client.get_calendar_service", return_value=mock_service):
        result = calendar_client.create_event(_plan())

    assert result.success is False
    assert result.error is not None
    assert result.event_id is None


def test_create_event_missing_client_secret_is_caught_not_raised():
    with patch(
        "modules.calendar_assistant.calendar_client.get_calendar_service",
        side_effect=FileNotFoundError("no client secret at ..."),
    ):
        result = calendar_client.create_event(_plan())

    assert result.success is False
    assert "no client secret" in result.error


def test_get_calendar_service_builds_once_and_caches():
    mock_creds = MagicMock()
    with patch(
        "modules.calendar_assistant.calendar_client._load_credentials", return_value=mock_creds
    ) as mock_load, patch(
        "modules.calendar_assistant.calendar_client.build", return_value=MagicMock()
    ) as mock_build:
        service1 = calendar_client.get_calendar_service()
        service2 = calendar_client.get_calendar_service()

    assert service1 is service2
    mock_load.assert_called_once()
    mock_build.assert_called_once()


def test_load_credentials_delegates_to_shared_google_auth_with_calendar_scope():
    # The actual OAuth cache/refresh/consent-flow logic is shared and tested once in
    # modules/tests/test_google_auth.py — this only checks calendar_client wires its
    # own least-privilege scope and token/secret paths into that shared loader.
    mock_creds = MagicMock()
    with patch(
        "modules.calendar_assistant.calendar_client._google_auth.load_credentials", return_value=mock_creds
    ) as mock_load:
        creds = calendar_client._load_credentials()

    assert creds is mock_creds
    mock_load.assert_called_once_with(
        calendar_client.SCOPES, calendar_client.CLIENT_SECRET_PATH, calendar_client.TOKEN_PATH
    )
