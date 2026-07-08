from unittest.mock import MagicMock, patch

from modules.form_filling import answer_missing_fields
from modules.form_filling.models import FieldSpec, FieldType


def _field(label: str, marker_id: str) -> FieldSpec:
    frame = MagicMock()
    frame.eval_on_selector.return_value = False  # "valid" after fill, by default
    return FieldSpec(
        marker_id=marker_id,
        frame=frame,
        selector=f"#{marker_id}",
        label=label,
        field_type=FieldType.TEXT,
    )


class _FakeWorker:
    def run(self, fn):
        return fn(page=None)


def test_no_missing_fields_short_circuits_without_matching():
    with patch("modules.form_filling.match_reply_to_fields") as mock_match:
        outcomes, still_missing, learned = answer_missing_fields(_FakeWorker(), [], "some reply")

    mock_match.assert_not_called()
    assert outcomes == []
    assert still_missing == []
    assert learned == {}


def test_reply_answering_nothing_leaves_all_fields_missing():
    fields = [_field("Phone Number", "a"), _field("How did you hear about us?", "b")]
    with patch("modules.form_filling.match_reply_to_fields", return_value={}):
        outcomes, still_missing, learned = answer_missing_fields(_FakeWorker(), fields, "unrelated reply")

    assert outcomes == []
    assert still_missing == fields
    assert learned == {}


def test_reply_answering_one_field_fills_it_and_leaves_the_other_missing():
    phone_field = _field("Phone Number", "a")
    referral_field = _field("How did you hear about us?", "b")
    fields = [phone_field, referral_field]

    with patch("modules.form_filling.match_reply_to_fields", return_value={"a": "9876543210"}):
        outcomes, still_missing, learned = answer_missing_fields(
            _FakeWorker(), fields, "my phone is 9876543210"
        )

    assert len(outcomes) == 1
    assert outcomes[0].field.marker_id == "a"
    assert outcomes[0].success is True
    phone_field.frame.fill.assert_called_once_with("#a", "9876543210", timeout=8000)

    assert still_missing == [referral_field]
    assert learned == {"phone number": "9876543210"}


def test_failed_fill_is_reported_not_raised():
    from playwright.sync_api import Error as PlaywrightError

    field = _field("Phone Number", "a")
    field.frame.fill.side_effect = PlaywrightError("boom")

    with patch("modules.form_filling.match_reply_to_fields", return_value={"a": "9876543210"}):
        outcomes, still_missing, learned = answer_missing_fields(_FakeWorker(), [field], "my phone is 9876543210")

    assert outcomes[0].success is False
    assert "boom" in outcomes[0].error
    assert still_missing == []
    # Still recorded as "learned" even though the live fill failed — the answer
    # itself is valid and worth remembering for the next form.
    assert learned == {"phone number": "9876543210"}
