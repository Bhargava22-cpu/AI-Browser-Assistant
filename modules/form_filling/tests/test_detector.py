from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from modules.form_filling.detector import detect_fields
from modules.form_filling.models import FieldType

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "main_form.html"


@pytest.fixture(scope="module")
def detected_fields():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{FIXTURE_PATH}")
        fields, warnings = detect_fields(page)
        yield fields, warnings
        browser.close()


def _by_label(fields, substring: str):
    matches = [f for f in fields if substring.lower() in f.label.lower()]
    assert matches, f"no field found with label containing '{substring}' among {[f.label for f in fields]}"
    return matches[0]


def test_detects_fields_in_main_frame(detected_fields):
    fields, _ = detected_fields
    main_frame_fields = [f for f in fields if f.frame.url.endswith("main_form.html")]
    assert len(main_frame_fields) >= 9  # name, email, phone, skills, state, newsletter, 2 radios, resume, sop


def test_detects_fields_in_nested_iframe(detected_fields):
    fields, _ = detected_fields
    iframe_fields = [f for f in fields if f.frame.url.endswith("nested_form.html")]
    assert len(iframe_fields) == 2
    labels = {f.label for f in iframe_fields}
    assert any("hear about" in label.lower() for label in labels)
    assert any("cover letter" in label.lower() for label in labels)


def test_label_resolution_via_native_label_for(detected_fields):
    fields, _ = detected_fields
    field = _by_label(fields, "Full Name")
    assert field.field_type == FieldType.TEXT


def test_label_resolution_via_aria_label(detected_fields):
    fields, _ = detected_fields
    field = _by_label(fields, "Phone Number")
    assert field.field_type == FieldType.TEXT


def test_label_resolution_via_placeholder(detected_fields):
    fields, _ = detected_fields
    field = _by_label(fields, "skills, comma separated")
    assert field.field_type == FieldType.TEXT


def test_select_options_captured(detected_fields):
    fields, _ = detected_fields
    field = _by_label(fields, "State")
    assert field.field_type == FieldType.SELECT
    assert "Maharashtra" in field.options


def test_file_field_detected(detected_fields):
    fields, _ = detected_fields
    field = _by_label(fields, "Resume")
    assert field.field_type == FieldType.FILE


def test_marker_selector_assigned_when_no_native_id(detected_fields):
    fields, _ = detected_fields
    field = _by_label(fields, "Phone Number")
    assert field.selector.startswith("[data-agent-field-id=")


def test_native_id_used_as_selector_when_present(detected_fields):
    fields, _ = detected_fields
    field = _by_label(fields, "Full Name")
    assert field.selector == "#full-name"


def test_disabled_field_is_not_detected(detected_fields):
    fields, _ = detected_fields
    assert not any("referral code" in f.label.lower() for f in fields)
