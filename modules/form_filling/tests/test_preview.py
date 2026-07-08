from unittest.mock import MagicMock

from playwright.sync_api import Error as PlaywrightError

from modules.form_filling import preview as preview_module
from modules.form_filling.models import FieldPlan, FieldSource, FieldSpec, FieldType
from modules.form_filling.preview import build_preview


def _plan(label: str, value, source: FieldSource) -> FieldPlan:
    field = FieldSpec(
        marker_id=label,
        frame=MagicMock(),
        selector=f"#{label}",
        label=label,
        field_type=FieldType.TEXT,
    )
    return FieldPlan(field=field, value=value, source=source)


def test_build_preview_takes_screenshot_and_builds_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(preview_module, "SCREENSHOTS_DIR", tmp_path / "screenshots")
    page = MagicMock()
    plans = [
        _plan("Full Name", "Arjun Mehta", FieldSource.PROFILE),
        _plan("SOP", "A generated answer", FieldSource.GENERATED),
        _plan("Gender", None, FieldSource.MISSING),
    ]

    result = build_preview(page, "task-1", plans)

    expected_path = str(tmp_path / "screenshots" / "task-1.png")
    page.screenshot.assert_called_once_with(path=expected_path, full_page=True)
    assert result.screenshot_path == expected_path
    assert len(result.entries) == 3
    assert result.entries[0].label == "Full Name"
    assert result.entries[0].value == "Arjun Mehta"
    assert result.entries[1].source == FieldSource.GENERATED
    assert result.entries[2].value == ""  # missing fields have blank preview value


def test_build_preview_creates_screenshots_dir_if_missing(tmp_path, monkeypatch):
    target_dir = tmp_path / "nested" / "screenshots"
    monkeypatch.setattr(preview_module, "SCREENSHOTS_DIR", target_dir)
    page = MagicMock()

    build_preview(page, "task-2", [])

    assert target_dir.exists()


def test_screenshot_failure_returns_none_path_but_still_builds_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(preview_module, "SCREENSHOTS_DIR", tmp_path / "screenshots")
    page = MagicMock()
    page.screenshot.side_effect = PlaywrightError("page closed")
    plans = [_plan("Email", "a@b.com", FieldSource.PROFILE)]

    result = build_preview(page, "task-3", plans)

    assert result.screenshot_path is None
    assert len(result.entries) == 1
    assert result.entries[0].value == "a@b.com"


def test_field_label_falls_back_to_selector_when_label_empty():
    field = FieldSpec(marker_id="m1", frame=MagicMock(), selector="#weird-field", label="", field_type=FieldType.TEXT)
    plan = FieldPlan(field=field, value="x", source=FieldSource.PROFILE)
    page = MagicMock()

    result = build_preview(page, "task-4", [plan])

    assert result.entries[0].label == "#weird-field"
