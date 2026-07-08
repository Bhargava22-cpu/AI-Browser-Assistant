from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from .models import FieldPlan, FieldSource, PreviewEntry, PreviewResult

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"


def build_preview(page: Page, task_id: str, plans: list[FieldPlan]) -> PreviewResult:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path: str | None = None

    try:
        path = SCREENSHOTS_DIR / f"{task_id}.png"
        page.screenshot(path=str(path), full_page=True)
        screenshot_path = str(path)
    except PlaywrightError:
        screenshot_path = None

    entries = [
        PreviewEntry(
            label=plan.field.label or plan.field.selector,
            value="" if plan.source == FieldSource.MISSING else str(plan.value),
            source=plan.source,
        )
        for plan in plans
    ]

    return PreviewResult(screenshot_path=screenshot_path, entries=entries)
