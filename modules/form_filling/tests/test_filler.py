from unittest.mock import MagicMock

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from modules.form_filling.filler import apply_field_plan
from modules.form_filling.models import FieldPlan, FieldSource, FieldSpec, FieldType


def _plan(field_type: FieldType, value, source=FieldSource.PROFILE, marker_id="m1") -> FieldPlan:
    frame = MagicMock()
    frame.eval_on_selector.return_value = False  # "valid" by default — most tests don't care
    field = FieldSpec(
        marker_id=marker_id,
        frame=frame,
        selector=f"#{marker_id}",
        label=marker_id,
        field_type=field_type,
    )
    return FieldPlan(field=field, value=value, source=source)


def test_text_field_calls_fill():
    plan = _plan(FieldType.TEXT, "Arjun Mehta")

    outcomes, warnings = apply_field_plan([plan])

    plan.field.frame.fill.assert_called_once_with(
        plan.field.selector, "Arjun Mehta", timeout=8000
    )
    assert outcomes[0].success is True
    assert not warnings


def test_textarea_field_calls_fill():
    plan = _plan(FieldType.TEXTAREA, "Some long generated text")

    apply_field_plan([plan])

    plan.field.frame.fill.assert_called_once_with(
        plan.field.selector, "Some long generated text", timeout=8000
    )


def test_select_field_calls_select_option_by_label():
    plan = _plan(FieldType.SELECT, "Maharashtra")

    apply_field_plan([plan])

    plan.field.frame.select_option.assert_called_once_with(
        plan.field.selector, label="Maharashtra", timeout=8000
    )


def test_checkbox_truthy_calls_check():
    plan = _plan(FieldType.CHECKBOX, True)

    apply_field_plan([plan])

    plan.field.frame.check.assert_called_once_with(plan.field.selector, timeout=8000)
    plan.field.frame.uncheck.assert_not_called()


def test_checkbox_falsy_calls_uncheck():
    plan = _plan(FieldType.CHECKBOX, False)

    apply_field_plan([plan])

    plan.field.frame.uncheck.assert_called_once_with(plan.field.selector, timeout=8000)
    plan.field.frame.check.assert_not_called()


def test_radio_truthy_calls_check():
    plan = _plan(FieldType.RADIO, "Male")

    apply_field_plan([plan])

    plan.field.frame.check.assert_called_once_with(plan.field.selector, timeout=8000)


def test_radio_falsy_is_skipped_without_error():
    plan = _plan(FieldType.RADIO, "")

    outcomes, warnings = apply_field_plan([plan])

    plan.field.frame.check.assert_not_called()
    assert outcomes == []
    assert not warnings


def test_file_field_is_skipped():
    plan = _plan(FieldType.FILE, "/tmp/resume.pdf")

    outcomes, warnings = apply_field_plan([plan])

    assert outcomes == []
    assert not warnings


def test_missing_source_is_skipped():
    plan = _plan(FieldType.TEXT, None, source=FieldSource.MISSING)

    outcomes, warnings = apply_field_plan([plan])

    plan.field.frame.fill.assert_not_called()
    assert outcomes == []


def test_none_value_is_skipped_even_if_source_is_profile():
    plan = _plan(FieldType.TEXT, None, source=FieldSource.PROFILE)

    outcomes, warnings = apply_field_plan([plan])

    plan.field.frame.fill.assert_not_called()
    assert outcomes == []


def test_timeout_error_recorded_as_failed_outcome():
    plan = _plan(FieldType.TEXT, "value")
    plan.field.frame.fill.side_effect = PlaywrightTimeoutError("timed out")

    outcomes, warnings = apply_field_plan([plan])

    assert outcomes[0].success is False
    assert "timed out" in outcomes[0].error
    assert warnings


def test_playwright_error_recorded_as_failed_outcome():
    plan = _plan(FieldType.SELECT, "Unknown Option")
    plan.field.frame.select_option.side_effect = PlaywrightError("no such option")

    outcomes, warnings = apply_field_plan([plan])

    assert outcomes[0].success is False
    assert "no such option" in outcomes[0].error


def test_one_failure_does_not_block_remaining_plans():
    failing = _plan(FieldType.TEXT, "value", marker_id="a")
    failing.field.frame.fill.side_effect = PlaywrightError("boom")
    ok = _plan(FieldType.TEXT, "value2", marker_id="b")

    outcomes, warnings = apply_field_plan([failing, ok])

    assert len(outcomes) == 2
    assert outcomes[0].success is False
    assert outcomes[1].success is True


def test_transient_error_is_retried_and_recovers():
    plan = _plan(FieldType.TEXT, "value")
    plan.field.frame.fill.side_effect = [PlaywrightError("boom"), None]

    outcomes, warnings = apply_field_plan([plan])

    assert plan.field.frame.fill.call_count == 2
    assert outcomes[0].success is True
    assert not warnings


def test_field_reporting_invalid_after_fill_fails_without_retrying_fill():
    # Retyping the same value again can't fix a validation error, so a field that
    # still reports itself invalid after a successful fill is reported directly —
    # no second fill attempt.
    plan = _plan(FieldType.TEXT, "value")
    plan.field.frame.eval_on_selector.return_value = True

    outcomes, warnings = apply_field_plan([plan])

    assert plan.field.frame.fill.call_count == 1
    assert outcomes[0].success is False
    assert "validation" in outcomes[0].error
    assert warnings


def test_eval_on_selector_error_is_treated_as_valid():
    plan = _plan(FieldType.TEXT, "value")
    plan.field.frame.eval_on_selector.side_effect = PlaywrightError("no such method")

    outcomes, warnings = apply_field_plan([plan])

    assert outcomes[0].success is True
    assert not warnings
