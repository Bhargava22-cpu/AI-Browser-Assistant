from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .models import FieldPlan, FieldSource, FieldType, FillOutcome

_TRUTHY_STRINGS = {"true", "yes", "y", "1"}
_ACTION_TIMEOUT_MS = 8000
_RETRY_ATTEMPTS = 2  # 1 retry for transient failures only — retyping the same value
# again can't fix a validation error, so that's reported directly instead of retried

_INVALID_CHECK_JS = (
    "el => (el.checkValidity ? !el.checkValidity() : false) "
    "|| el.getAttribute('aria-invalid') === 'true'"
)


def _is_truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY_STRINGS or bool(value.strip())
    return bool(value)


def _perform_action(field, plan: FieldPlan) -> None:
    if field.field_type in (FieldType.TEXT, FieldType.TEXTAREA):
        field.frame.fill(field.selector, str(plan.value), timeout=_ACTION_TIMEOUT_MS)
    elif field.field_type == FieldType.SELECT:
        field.frame.select_option(field.selector, label=str(plan.value), timeout=_ACTION_TIMEOUT_MS)
    elif field.field_type == FieldType.CHECKBOX:
        if _is_truthy(plan.value):
            field.frame.check(field.selector, timeout=_ACTION_TIMEOUT_MS)
        else:
            field.frame.uncheck(field.selector, timeout=_ACTION_TIMEOUT_MS)
    elif field.field_type == FieldType.RADIO:
        selector = field.selector
        if field.option_selectors:
            chosen = str(plan.value).strip()
            selector = field.option_selectors.get(chosen)
            if selector is None:
                # Case-insensitive fallback — LLM/reply-matcher answers are asked to
                # echo an option verbatim, but exact casing isn't guaranteed.
                for option_label, option_selector in field.option_selectors.items():
                    if option_label.strip().lower() == chosen.lower():
                        selector = option_selector
                        break
            if selector is None:
                raise ValueError(
                    f"no matching radio option for {plan.value!r} "
                    f"(options: {list(field.option_selectors)})"
                )
        field.frame.check(selector, timeout=_ACTION_TIMEOUT_MS)
    else:
        raise ValueError(f"unsupported field_type: {field.field_type}")


def _reports_invalid(field) -> bool:
    """Best-effort native validation check (checkValidity/aria-invalid) after a fill.
    A Playwright error here just means we can't tell — don't treat that as invalid."""
    try:
        return bool(field.frame.eval_on_selector(field.selector, _INVALID_CHECK_JS))
    except (PlaywrightTimeoutError, PlaywrightError):
        return False


def _fill_one(field, plan: FieldPlan) -> str | None:
    """Perform the field's action, retrying transient Playwright failures once,
    then check native validation. Returns an error message, or None on success."""
    error: str | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            _perform_action(field, plan)
            error = None
            break
        except (PlaywrightTimeoutError, PlaywrightError) as e:
            error = str(e)
        except ValueError as e:
            return str(e)  # unsupported field type — retrying changes nothing

    if error:
        return error
    if _reports_invalid(field):
        return "field failed native validation (checkValidity/aria-invalid) after fill"
    return None


def apply_field_plan(plans: list[FieldPlan]) -> tuple[list[FillOutcome], list[str]]:
    outcomes: list[FillOutcome] = []
    warnings: list[str] = []

    for plan in plans:
        if plan.source == FieldSource.MISSING or plan.value is None:
            continue

        field = plan.field
        if field.field_type == FieldType.FILE:
            continue  # handled by upload.py
        if field.field_type == FieldType.RADIO and not _is_truthy(plan.value):
            continue

        error = _fill_one(field, plan)
        outcomes.append(FillOutcome(field=field, success=error is None, error=error))
        if error:
            warnings.append(f"Failed to fill '{field.label or field.selector}': {error}")

    return outcomes, warnings
