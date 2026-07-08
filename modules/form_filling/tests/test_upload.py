from unittest.mock import MagicMock

from playwright.sync_api import Error as PlaywrightError

from modules.form_filling.models import FieldSpec, FieldType
from modules.form_filling.upload import upload_resume


def _file_field(marker_id: str = "f1") -> FieldSpec:
    return FieldSpec(
        marker_id=marker_id,
        frame=MagicMock(),
        selector=f"#{marker_id}",
        label="Resume",
        field_type=FieldType.FILE,
    )


def _text_field() -> FieldSpec:
    return FieldSpec(
        marker_id="t1",
        frame=MagicMock(),
        selector="#t1",
        label="Full Name",
        field_type=FieldType.TEXT,
    )


def test_no_file_fields_returns_not_attempted():
    outcome = upload_resume([_text_field()], {"resume_path": "/tmp/resume.pdf"})

    assert outcome.attempted is False
    assert outcome.success is False


def test_missing_resume_path_in_profile():
    outcome = upload_resume([_file_field()], {})

    assert outcome.attempted is False
    assert outcome.success is False
    assert outcome.error == "No resume_path in profile"


def test_resume_file_does_not_exist_on_disk():
    field = _file_field()

    outcome = upload_resume([field], {"resume_path": "/nonexistent/path/resume.pdf"})

    assert outcome.attempted is True
    assert outcome.success is False
    assert "not found" in outcome.error
    field.frame.set_input_files.assert_not_called()


def test_successful_upload_calls_set_input_files(tmp_path):
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 fake resume")
    field = _file_field()

    outcome = upload_resume([field], {"resume_path": str(resume_path)})

    field.frame.set_input_files.assert_called_once_with(field.selector, str(resume_path))
    assert outcome.attempted is True
    assert outcome.success is True
    assert outcome.file_path == str(resume_path)


def test_playwright_error_during_upload_is_captured(tmp_path):
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 fake resume")
    field = _file_field()
    field.frame.set_input_files.side_effect = PlaywrightError("upload rejected")

    outcome = upload_resume([field], {"resume_path": str(resume_path)})

    assert outcome.attempted is True
    assert outcome.success is False
    assert "upload rejected" in outcome.error


def test_only_first_file_field_is_used():
    field1 = _file_field(marker_id="f1")
    field2 = _file_field(marker_id="f2")

    outcome = upload_resume([field1, field2], {"resume_path": "/nonexistent/resume.pdf"})

    field2.frame.set_input_files.assert_not_called()
    assert outcome.attempted is True
