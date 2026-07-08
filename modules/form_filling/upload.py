from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

from .models import FieldSpec, FieldType, UploadOutcome


def upload_resume(fields: list[FieldSpec], profile_flat: dict) -> UploadOutcome:
    file_fields = [f for f in fields if f.field_type == FieldType.FILE]
    if not file_fields:
        return UploadOutcome(attempted=False, success=False)

    resume_path = profile_flat.get("resume_path", "")
    if not resume_path:
        return UploadOutcome(attempted=False, success=False, error="No resume_path in profile")

    field = file_fields[0]

    try:
        if not Path(resume_path).exists():
            raise FileNotFoundError(f"Resume file not found: {resume_path}")
        field.frame.set_input_files(field.selector, resume_path)
        return UploadOutcome(attempted=True, success=True, file_path=resume_path)
    except FileNotFoundError as e:
        return UploadOutcome(attempted=True, success=False, file_path=resume_path, error=str(e))
    except PlaywrightError as e:
        return UploadOutcome(attempted=True, success=False, file_path=resume_path, error=str(e))
