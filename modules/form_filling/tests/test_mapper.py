import json
from unittest.mock import MagicMock, patch

from modules.form_filling.mapper import map_fields_to_profile
from modules.form_filling.models import FieldSource, FieldSpec, FieldType


def _field(label: str, field_type: FieldType = FieldType.TEXT, marker_id: str = "m1") -> FieldSpec:
    return FieldSpec(
        marker_id=marker_id,
        frame=None,
        selector=f"#{marker_id}",
        label=label,
        field_type=field_type,
    )


def _profile_flat() -> dict:
    return {
        "name": "Arjun Mehta",
        "email": "arjun.mehta@example.com",
        "phone": "+91-9876543210",
        "address_state": "Maharashtra",
        "skills": "Python, JavaScript",
    }


def _mock_llm_response(decisions: dict) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = json.dumps(decisions)
    mock_result = MagicMock()
    mock_result.choices = [MagicMock(message=mock_message)]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result
    return mock_client


def test_heuristic_match_skips_llm_entirely():
    fields = [_field("Email Address", marker_id="a"), _field("Phone Number", marker_id="b")]

    with patch("modules.form_filling.mapper._client_instance") as mock_instance:
        plans, warnings = map_fields_to_profile(fields, _profile_flat())

    mock_instance.assert_not_called()
    assert not warnings
    by_marker = {p.field.marker_id: p for p in plans}
    assert by_marker["a"].source == FieldSource.PROFILE
    assert by_marker["a"].value == "arjun.mehta@example.com"
    assert by_marker["b"].value == "+91-9876543210"


def test_heuristic_keyword_match_with_empty_profile_value_falls_back_to_llm():
    fields = [_field("College Name", marker_id="c")]
    profile = _profile_flat()  # no "college" key

    mock_client = _mock_llm_response({"c": {"action": "missing"}})
    with patch("modules.form_filling.mapper._client_instance", return_value=mock_client):
        plans, warnings = map_fields_to_profile(fields, profile)

    assert mock_client.chat.completions.create.called
    assert plans[0].source == FieldSource.MISSING


def test_llm_generate_action():
    fields = [_field("Why do you want this role?", marker_id="g")]
    mock_client = _mock_llm_response({"g": {"action": "generate"}})

    with patch("modules.form_filling.mapper._client_instance", return_value=mock_client):
        plans, warnings = map_fields_to_profile(fields, _profile_flat())

    assert plans[0].source == FieldSource.GENERATED
    assert plans[0].value is None


def test_llm_profile_action_with_valid_key():
    fields = [_field("State", field_type=FieldType.SELECT, marker_id="s")]
    mock_client = _mock_llm_response({"s": {"action": "profile", "profile_key": "address_state"}})

    with patch("modules.form_filling.mapper._client_instance", return_value=mock_client):
        plans, warnings = map_fields_to_profile(fields, _profile_flat())

    assert plans[0].source == FieldSource.PROFILE
    assert plans[0].value == "Maharashtra"


def test_llm_profile_action_with_missing_key_falls_back_to_missing():
    fields = [_field("Mystery Field", marker_id="x")]
    mock_client = _mock_llm_response({"x": {"action": "profile", "profile_key": "nonexistent_key"}})

    with patch("modules.form_filling.mapper._client_instance", return_value=mock_client):
        plans, warnings = map_fields_to_profile(fields, _profile_flat())

    assert plans[0].source == FieldSource.MISSING


def test_llm_api_error_marks_remaining_fields_missing_with_warning():
    from groq import APIError

    fields = [_field("Newsletter", field_type=FieldType.CHECKBOX, marker_id="n")]
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = APIError(
        "boom", request=MagicMock(), body=None
    )

    with patch("modules.form_filling.mapper._client_instance", return_value=mock_client):
        plans, warnings = map_fields_to_profile(fields, _profile_flat())

    assert plans[0].source == FieldSource.MISSING
    assert warnings and "LLM field mapping failed" in warnings[0]


def test_llm_malformed_json_marks_remaining_fields_missing_with_warning():
    mock_message = MagicMock()
    mock_message.content = "not valid json{{"
    mock_result = MagicMock()
    mock_result.choices = [MagicMock(message=mock_message)]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_result

    fields = [_field("Referral Source", marker_id="r")]
    with patch("modules.form_filling.mapper._client_instance", return_value=mock_client):
        plans, warnings = map_fields_to_profile(fields, _profile_flat())

    assert plans[0].source == FieldSource.MISSING
    assert warnings and "LLM field mapping failed" in warnings[0]


def test_file_fields_are_excluded_from_mapping():
    fields = [_field("Resume", field_type=FieldType.FILE, marker_id="f")]

    with patch("modules.form_filling.mapper._client_instance") as mock_instance:
        plans, warnings = map_fields_to_profile(fields, _profile_flat())

    mock_instance.assert_not_called()
    assert plans == []


def test_learned_field_match_skips_llm_and_heuristic():
    fields = [_field("How did you hear about us?", marker_id="h")]
    learned = {"how did you hear about us?": "Referred by a friend"}

    with patch("modules.form_filling.mapper._client_instance") as mock_instance:
        plans, warnings = map_fields_to_profile(fields, _profile_flat(), learned)

    mock_instance.assert_not_called()
    assert not warnings
    assert plans[0].source == FieldSource.PROFILE
    assert plans[0].value == "Referred by a friend"


def test_learned_field_match_is_normalized_for_whitespace_and_case():
    fields = [_field("  How Did You   Hear About Us?  ", marker_id="h")]
    learned = {"how did you hear about us?": "Referred by a friend"}

    plans, warnings = map_fields_to_profile(fields, _profile_flat(), learned)

    assert plans[0].value == "Referred by a friend"


def test_no_learned_fields_falls_through_to_heuristic():
    fields = [_field("Email Address", marker_id="a")]

    plans, warnings = map_fields_to_profile(fields, _profile_flat(), learned_fields=None)

    assert plans[0].source == FieldSource.PROFILE
    assert plans[0].value == "arjun.mehta@example.com"
