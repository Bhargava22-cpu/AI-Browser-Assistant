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
    frame: Frame  # live reference — safe only because the whole pipeline runs inside one worker.run() call
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
