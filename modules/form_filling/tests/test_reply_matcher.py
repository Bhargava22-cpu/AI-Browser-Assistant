import json
from unittest.mock import MagicMock, patch

from modules.form_filling.models import FieldSpec, FieldType
from modules.form_filling.reply_matcher import match_reply_to_fields


def _field(label: str, field_type: FieldType = FieldType.TEXT, marker_id: str = "m1", options=None) -> FieldSpec:
    return FieldSpec(
        marker_id=marker_id,
        frame=None,
        selector=f"#{marker_id}",
        label=label,
        field_type=field_type,
        options=options or [],
    )


def _mock_llm_response(decisions: dict) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = json.dumps(decisions)
    mock_result = MagicMock()
    mock_result.choices = [MagicMock(message=mock_message)]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result
    return mock_client


def test_empty_reply_or_no_fields_skips_llm_entirely():
    with patch("modules.form_filling.reply_matcher._client_instance") as mock_instance:
        assert match_reply_to_fields("", [_field("Phone")]) == {}
        assert match_reply_to_fields("my phone is 123", []) == {}

    mock_instance.assert_not_called()


def test_matches_answered_field_only():
    fields = [_field("How did you hear about us?", marker_id="a"), _field("Phone Number", marker_id="b")]
    mock_client = _mock_llm_response({"a": "LinkedIn"})
    with patch("modules.form_filling.reply_matcher._client_instance", return_value=mock_client):
        result = match_reply_to_fields("I found out via LinkedIn", fields)

    assert result == {"a": "LinkedIn"}


def test_filters_out_marker_ids_not_in_the_given_fields():
    fields = [_field("Phone Number", marker_id="b")]
    mock_client = _mock_llm_response({"a": "LinkedIn", "b": "9876543210"})
    with patch("modules.form_filling.reply_matcher._client_instance", return_value=mock_client):
        result = match_reply_to_fields("my phone is 9876543210", fields)

    assert result == {"b": "9876543210"}


def test_llm_error_returns_empty_dict_not_raise():
    from groq import APIError

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = APIError("boom", request=MagicMock(), body=None)
    with patch("modules.form_filling.reply_matcher._client_instance", return_value=mock_client):
        result = match_reply_to_fields("my phone is 123", [_field("Phone")])

    assert result == {}


def test_malformed_json_returns_empty_dict_not_raise():
    mock_message = MagicMock()
    mock_message.content = "not json"
    mock_result = MagicMock()
    mock_result.choices = [MagicMock(message=mock_message)]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result

    with patch("modules.form_filling.reply_matcher._client_instance", return_value=mock_client):
        result = match_reply_to_fields("my phone is 123", [_field("Phone")])

    assert result == {}
