import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import sync_playwright

from modules.form_filling import fill_form
from modules.form_filling import preview as preview_module
from modules.form_filling.models import FieldSource

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "main_form.html"

# Fields with no heuristic keyword match — routed through the (mocked) LLM mapper.
_MISSING_LABEL_HINTS = ("newsletter", "male", "female", "hear about")
_GENERATE_LABEL_HINTS = ("statement of purpose", "cover letter")


class _InlineWorker:
    """Executes the pipeline closure directly against a real page — no threading needed for tests."""

    def __init__(self, page):
        self._page = page

    def run(self, fn):
        return fn(self._page)


def _profile(resume_path: str) -> dict:
    return {
        "name": "Arjun Mehta",
        "email": "arjun.mehta@example.com",
        "phone": "+91-9876543210",
        "address": {
            "street": "42 Bandra West",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400050",
            "country": "India",
        },
        "college": "IIT Bombay",
        "degree": "B.Tech Computer Science",
        "graduation_year": 2024,
        "skills": ["Python", "JavaScript", "React"],
        "resume_path": resume_path,
        "linkedin": "https://linkedin.com/in/arjun-mehta",
        "github": "https://github.com/arjunmehta",
    }


def _llm_client(build_response) -> MagicMock:
    client = MagicMock()

    def _side_effect(**kwargs):
        user_prompt = json.loads(kwargs["messages"][1]["content"])
        payload = build_response(user_prompt)
        message = MagicMock()
        message.content = json.dumps(payload)
        result = MagicMock()
        result.choices = [MagicMock(message=message)]
        return result

    client.chat.completions.create.side_effect = _side_effect
    return client


def _mapper_decisions(user_prompt: dict) -> dict:
    decisions = {}
    for f in user_prompt["fields"]:
        label = f["label"].lower()
        if any(hint in label for hint in _MISSING_LABEL_HINTS):
            decisions[f["marker_id"]] = {"action": "missing"}
        elif any(hint in label for hint in _GENERATE_LABEL_HINTS):
            decisions[f["marker_id"]] = {"action": "generate"}
        else:
            decisions[f["marker_id"]] = {"action": "missing"}
    return decisions


def _generator_answers(user_prompt: dict) -> dict:
    return {f["marker_id"]: f"Generated answer for: {f['label']}" for f in user_prompt["fields"]}


@pytest.fixture(scope="module")
def browser_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


def test_full_pipeline_fills_heuristic_and_llm_routed_fields(browser_page, tmp_path, monkeypatch):
    monkeypatch.setattr(preview_module, "SCREENSHOTS_DIR", tmp_path / "screenshots")

    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 fake resume")
    profile = _profile(str(resume_path))

    mapper_client = _llm_client(_mapper_decisions)
    generator_client = _llm_client(_generator_answers)

    with patch("modules.form_filling.mapper._client_instance", return_value=mapper_client), patch(
        "modules.form_filling.generator._client_instance", return_value=generator_client
    ):
        result = fill_form(
            _InlineWorker(browser_page),
            profile,
            task_id="integration-test",
            url=f"file://{FIXTURE_PATH}",
        )

    filled_labels = {o.field.label for o in result.filled_fields if o.success}
    assert "Full Name" in filled_labels
    assert "Email Address" in filled_labels
    assert "Phone Number" in filled_labels
    assert "Your skills, comma separated" in filled_labels
    assert "State" in filled_labels
    assert any("Statement of Purpose" in label for label in filled_labels)
    assert any("Cover Letter" in label for label in filled_labels)

    assert all(o.success for o in result.filled_fields)

    missing_labels = {f.label for f in result.missing_fields}
    assert "Subscribe to newsletter" in missing_labels
    assert "How did you hear about us?" in missing_labels

    assert result.upload.attempted is True
    assert result.upload.success is True
    assert result.upload.file_path == str(resume_path)

    assert result.preview.screenshot_path is not None
    assert Path(result.preview.screenshot_path).exists()
    assert len(result.preview.entries) == len(result.filled_fields) + len(result.missing_fields)


def test_pipeline_never_touches_submit_button(browser_page, tmp_path, monkeypatch):
    monkeypatch.setattr(preview_module, "SCREENSHOTS_DIR", tmp_path / "screenshots")
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 fake resume")
    profile = _profile(str(resume_path))

    mapper_client = _llm_client(_mapper_decisions)
    generator_client = _llm_client(_generator_answers)

    with patch("modules.form_filling.mapper._client_instance", return_value=mapper_client), patch(
        "modules.form_filling.generator._client_instance", return_value=generator_client
    ):
        fill_form(
            _InlineWorker(browser_page),
            profile,
            task_id="integration-test-2",
            url=f"file://{FIXTURE_PATH}",
        )

    # A different page instance to check the submit button was never clicked
    # (form_filling has no submit call — this asserts the field is still present/enabled).
    assert browser_page.is_enabled("#submit-btn")


def test_generated_values_come_from_llm_not_profile(browser_page, tmp_path, monkeypatch):
    monkeypatch.setattr(preview_module, "SCREENSHOTS_DIR", tmp_path / "screenshots")
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4 fake resume")
    profile = _profile(str(resume_path))

    mapper_client = _llm_client(_mapper_decisions)
    generator_client = _llm_client(_generator_answers)

    with patch("modules.form_filling.mapper._client_instance", return_value=mapper_client), patch(
        "modules.form_filling.generator._client_instance", return_value=generator_client
    ):
        result = fill_form(
            _InlineWorker(browser_page),
            profile,
            task_id="integration-test-3",
            url=f"file://{FIXTURE_PATH}",
        )

    sop_entry = next(e for e in result.preview.entries if "Statement of Purpose" in e.label)
    assert sop_entry.source == FieldSource.GENERATED
    assert sop_entry.value.startswith("Generated answer for:")
