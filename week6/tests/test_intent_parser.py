"""
6 pytest tests for the Week 3 intent parser — one per action type.
The Groq API call is mocked so tests run offline and deterministically.
"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Allow imports from week3/scripts/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "week3" / "scripts"))
from intent_parser import parse_intent  # noqa: E402


def _mock_groq_response(action_dict: dict):
    """Build a mock AsyncGroq client whose create() returns the given dict as JSON."""
    mock_result = MagicMock()
    mock_result.choices[0].message.content = json.dumps(action_dict)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_result)
    return mock_client


# ── helpers ──────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.run(coro)


# ── 1. navigate ───────────────────────────────────────────────────────────────

def test_navigate_action():
    expected = {
        "action": "navigate",
        "target_url": "https://github.com",
        "data": {"search_query": "Python"},
        "steps": ["Open GitHub", "Search for Python"],
    }
    with patch("intent_parser._client_instance", return_value=_mock_groq_response(expected)):
        result = run(parse_intent("go to github.com and search for Python projects"))

    assert result["action"] == "navigate"
    assert "target_url" in result
    assert isinstance(result["steps"], list)
    assert len(result["steps"]) > 0


# ── 2. fill_form ──────────────────────────────────────────────────────────────

def test_fill_form_action():
    expected = {
        "action": "fill_form",
        "target_url": None,
        "data": {"source": "user_profile"},
        "steps": ["Detect form fields", "Load profile", "Fill fields"],
    }
    with patch("intent_parser._client_instance", return_value=_mock_groq_response(expected)):
        result = run(parse_intent("fill this internship application form with my details"))

    assert result["action"] == "fill_form"
    assert result["target_url"] is None
    assert "source" in result.get("data", {})


# ── 3. email ──────────────────────────────────────────────────────────────────

def test_email_action():
    expected = {
        "action": "email",
        "target_url": None,
        "data": {
            "recipient": "mentor",
            "subject": "Application Submitted",
            "body_intent": "inform mentor that I applied",
        },
        "steps": ["Look up mentor contact", "Draft email", "Show preview", "Send on confirmation"],
    }
    with patch("intent_parser._client_instance", return_value=_mock_groq_response(expected)):
        result = run(parse_intent("email my mentor that I applied to the internship"))

    assert result["action"] == "email"
    assert result["data"]["recipient"] == "mentor"
    assert "Send on confirmation" in result["steps"]


# ── 4. summarize ──────────────────────────────────────────────────────────────

def test_summarize_action():
    expected = {
        "action": "summarize",
        "target_url": None,
        "data": {"scope": "current_page"},
        "steps": ["Extract page content", "Send to LLM", "Return TL;DR"],
    }
    with patch("intent_parser._client_instance", return_value=_mock_groq_response(expected)):
        result = run(parse_intent("summarize the current page"))

    assert result["action"] == "summarize"
    assert result["data"]["scope"] == "current_page"


# ── 5. click ──────────────────────────────────────────────────────────────────

def test_click_action():
    expected = {
        "action": "click",
        "target_url": None,
        "data": {"element": "submit button"},
        "steps": ["Locate submit button", "Click it"],
    }
    with patch("intent_parser._client_instance", return_value=_mock_groq_response(expected)):
        result = run(parse_intent("click the submit button"))

    assert result["action"] == "click"
    assert result["data"]["element"] == "submit button"
    assert len(result["steps"]) == 2


# ── 6. calendar ───────────────────────────────────────────────────────────────

def test_calendar_action():
    expected = {
        "action": "calendar",
        "target_url": None,
        "data": {"schedule_request": "add DSA practice every day at 8pm for 2 weeks"},
        "steps": ["Parse the scheduling request", "Resolve dates and recurrence", "Show event preview", "Create event on confirmation"],
    }
    with patch("intent_parser._client_instance", return_value=_mock_groq_response(expected)):
        result = run(parse_intent("add DSA practice every day at 8pm for 2 weeks"))

    assert result["action"] == "calendar"
    assert "schedule_request" in result["data"]
