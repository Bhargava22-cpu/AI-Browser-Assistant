from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from modules.email_assistant import gmail_client
from modules.email_assistant.models import EmailDraftPlan


@pytest.fixture(autouse=True)
def reset_service_singleton():
    gmail_client._service = None
    yield
    gmail_client._service = None


def _draft() -> EmailDraftPlan:
    return EmailDraftPlan(to_email="mentor@example.com", subject="Hi", body="Body text")


def test_send_email_success():
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "msg123"
    }

    with patch("modules.email_assistant.gmail_client.get_gmail_service", return_value=mock_service):
        result = gmail_client.send_email(_draft())

    assert result.success is True
    assert result.message_id == "msg123"
    assert result.error is None


def test_send_email_http_error_is_caught_not_raised():
    mock_service = MagicMock()
    http_error = HttpError(resp=MagicMock(status=403), content=b'{"error": "forbidden"}')
    mock_service.users.return_value.messages.return_value.send.return_value.execute.side_effect = http_error

    with patch("modules.email_assistant.gmail_client.get_gmail_service", return_value=mock_service):
        result = gmail_client.send_email(_draft())

    assert result.success is False
    assert result.error is not None
    assert result.message_id is None


def test_send_email_missing_client_secret_is_caught_not_raised():
    with patch(
        "modules.email_assistant.gmail_client.get_gmail_service",
        side_effect=FileNotFoundError("no client secret at ..."),
    ):
        result = gmail_client.send_email(_draft())

    assert result.success is False
    assert "no client secret" in result.error


def test_build_raw_message_produces_base64_payload():
    raw = gmail_client._build_raw_message(_draft())
    assert set(raw.keys()) == {"raw"}
    assert isinstance(raw["raw"], str) and raw["raw"]


def test_get_gmail_service_builds_once_and_caches():
    mock_creds = MagicMock()
    with patch(
        "modules.email_assistant.gmail_client._load_credentials", return_value=mock_creds
    ) as mock_load, patch(
        "modules.email_assistant.gmail_client.build", return_value=MagicMock()
    ) as mock_build:
        service1 = gmail_client.get_gmail_service()
        service2 = gmail_client.get_gmail_service()

    assert service1 is service2
    mock_load.assert_called_once()
    mock_build.assert_called_once()


def test_load_credentials_delegates_to_shared_google_auth_with_gmail_scope():
    # The actual OAuth cache/refresh/consent-flow logic is shared and tested once in
    # modules/tests/test_google_auth.py — this only checks gmail_client wires its own
    # least-privilege scope and token/secret paths into that shared loader.
    mock_creds = MagicMock()
    with patch("modules.email_assistant.gmail_client._google_auth.load_credentials", return_value=mock_creds) as mock_load:
        creds = gmail_client._load_credentials()

    assert creds is mock_creds
    mock_load.assert_called_once_with(
        gmail_client.SCOPES, gmail_client.CLIENT_SECRET_PATH, gmail_client.TOKEN_PATH
    )
