import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from groq import APIError

from modules.email_assistant.composer import compose_email
from modules.email_assistant.models import EmailDraftPlan

_PROFILE = {"name": "Arjun Mehta", "email": "arjun.mehta@example.com"}


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


def test_invalid_recipient_raises_without_calling_llm():
    with patch("modules.email_assistant.composer._client_instance") as mock_instance:
        with pytest.raises(ValueError, match="doesn't look like an email address"):
            run(compose_email(_PROFILE, "my mentor", "tell them I applied"))

    mock_instance.assert_not_called()


def test_empty_body_intent_raises_without_calling_llm():
    with patch("modules.email_assistant.composer._client_instance") as mock_instance:
        with pytest.raises(ValueError, match="body_intent is required"):
            run(compose_email(_PROFILE, "mentor@example.com", ""))

    mock_instance.assert_not_called()


def test_successful_compose_uses_model_subject_when_no_hint():
    mock_client = _mock_llm_response(
        {"subject": "Application Submitted", "body": "Hi,\n\nJust letting you know...\n\nBest,\nArjun"}
    )
    with patch("modules.email_assistant.composer._client_instance", return_value=mock_client):
        draft = run(compose_email(_PROFILE, "mentor@example.com", "tell them I applied"))

    assert draft == EmailDraftPlan(
        to_email="mentor@example.com",
        subject="Application Submitted",
        body="Hi,\n\nJust letting you know...\n\nBest,\nArjun",
    )


def test_subject_hint_overrides_model_subject():
    mock_client = _mock_llm_response({"subject": "Model's guess", "body": "Body text"})
    with patch("modules.email_assistant.composer._client_instance", return_value=mock_client):
        draft = run(compose_email(
            _PROFILE, "mentor@example.com", "tell them I applied", subject_hint="Application Submitted"
        ))

    assert draft.subject == "Application Submitted"


def test_empty_body_from_llm_raises():
    mock_client = _mock_llm_response({"subject": "Hello", "body": ""})
    with patch("modules.email_assistant.composer._client_instance", return_value=mock_client):
        with pytest.raises(ValueError, match="empty email body"):
            run(compose_email(_PROFILE, "mentor@example.com", "tell them I applied"))


def test_groq_api_error_bubbles_as_value_error():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=APIError("boom", request=MagicMock(), body=None)
    )
    with patch("modules.email_assistant.composer._client_instance", return_value=mock_client):
        with pytest.raises(ValueError, match="Failed to compose email"):
            run(compose_email(_PROFILE, "mentor@example.com", "tell them I applied"))


def test_malformed_json_response_bubbles_as_value_error():
    mock_message = MagicMock()
    mock_message.content = "not json at all"
    mock_result = MagicMock()
    mock_result.choices = [MagicMock(message=mock_message)]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)

    with patch("modules.email_assistant.composer._client_instance", return_value=mock_client):
        with pytest.raises(ValueError, match="Failed to compose email"):
            run(compose_email(_PROFILE, "mentor@example.com", "tell them I applied"))
