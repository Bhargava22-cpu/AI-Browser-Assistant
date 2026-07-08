from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol

from playwright.sync_api import Frame, Page


class FieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    FILE = "file"


class FieldSource(str, Enum):
    PROFILE = "profile"
    GENERATED = "generated"
    MISSING = "missing"


@dataclass
class FieldSpec:
    marker_id: str
    frame: Frame  # live reference, tied to whatever page detected it. Safe to touch
    # from any thread as long as actual Playwright calls only ever happen inside a
    # worker.run() closure — fill_form()'s own pipeline is one such call, and
    # answer_missing_fields() is a second, later one reusing the same reference
    # (only valid as long as that page hasn't since navigated away).
    selector: str
    label: str
    field_type: FieldType
    required: bool = False
    options: list[str] = field(default_factory=list)
    placeholder: str = ""


@dataclass
class FieldPlan:
    field: FieldSpec
    value: Any
    source: FieldSource


@dataclass
class FillOutcome:
    field: FieldSpec
    success: bool
    error: str | None = None


@dataclass
class UploadOutcome:
    attempted: bool
    success: bool
    file_path: str | None = None
    error: str | None = None


@dataclass
class PreviewEntry:
    label: str
    value: str
    source: FieldSource


@dataclass
class PreviewResult:
    screenshot_path: str | None
    entries: list[PreviewEntry]


@dataclass
class FormFillResult:
    task_id: str
    url: str
    filled_fields: list[FillOutcome]
    missing_fields: list[FieldSpec]
    upload: UploadOutcome | None
    preview: PreviewResult
    warnings: list[str] = field(default_factory=list)


class BrowserWorkerProtocol(Protocol):
    def run(self, fn: Callable[[Page], Any]) -> Any: ...


def describe_fields_for_llm(fields: list[FieldSpec], include_required: bool = False) -> list[dict]:
    """Compact field descriptors for LLM prompts — marker_id, label, field_type,
    options, and optionally required. Shared by mapper.py's profile-mapping call
    and reply_matcher.py's reply-matching call, which each build their own prompt
    around the same underlying field shape."""
    descriptions = []
    for f in fields:
        d = {"marker_id": f.marker_id, "label": f.label, "field_type": f.field_type.value, "options": f.options}
        if include_required:
            d["required"] = f.required
        descriptions.append(d)
    return descriptions
