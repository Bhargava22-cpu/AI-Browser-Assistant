from playwright.sync_api import Page

from .detector import detect_fields
from .filler import apply_field_plan
from .generator import generate_long_text_batch
from .mapper import map_fields_to_profile
from .mapper import normalize_label
from .models import (
    BrowserWorkerProtocol,
    FieldPlan,
    FieldSource,
    FieldSpec,
    FillOutcome,
    FormFillResult,
    describe_missing_field,
)
from .preview import build_preview
from .profile_utils import flatten_profile
from .reply_matcher import match_reply_to_fields
from .upload import upload_resume

__all__ = [
    "fill_form",
    "normalize_label",
    "describe_fill_result",
    "describe_missing_field",
    "answer_missing_fields",
]


def fill_form(
    worker: BrowserWorkerProtocol,
    profile: dict,
    task_id: str,
    url: str | None = None,
) -> FormFillResult:
    """Single public entrypoint for Module 1 (Intelligent Form Filling).

    Runs the whole detect -> map -> generate -> fill -> upload -> preview
    pipeline as ONE closure passed to worker.run(), so it stays atomic
    relative to any other concurrent browser-tool call sharing the same
    worker/page. Never clicks submit — the caller decides what to do with
    the returned preview.

    `profile["learned_fields"]` (normalized_label -> answer, see `normalize_label`)
    is consulted before the heuristic/LLM mapping tiers — fields the user was asked
    about and answered on a prior run are filled automatically instead of coming
    back as missing. The caller is responsible for persisting new answers to
    still-missing fields back into that store between runs.
    """

    def _pipeline(page: Page) -> FormFillResult:
        warnings: list[str] = []

        if url:
            page.goto(url, timeout=20000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)

        profile_flat = flatten_profile(profile)
        learned_fields = profile.get("learned_fields") or {}

        fields, w1 = detect_fields(page)
        warnings.extend(w1)

        plans, w2 = map_fields_to_profile(fields, profile_flat, learned_fields)
        warnings.extend(w2)

        generate_targets = [p.field for p in plans if p.source == FieldSource.GENERATED]
        generated_text, w3 = generate_long_text_batch(generate_targets, profile_flat)
        warnings.extend(w3)

        for plan in plans:
            if plan.source == FieldSource.GENERATED:
                text = generated_text.get(plan.field.marker_id)
                if text:
                    plan.value = text
                else:
                    plan.source = FieldSource.MISSING

        outcomes, w4 = apply_field_plan(plans)
        warnings.extend(w4)

        upload_outcome = upload_resume(fields, profile_flat)

        preview = build_preview(page, task_id, plans)

        missing_fields = [p.field for p in plans if p.source == FieldSource.MISSING]

        return FormFillResult(
            task_id=task_id,
            url=page.url,
            filled_fields=outcomes,
            missing_fields=missing_fields,
            upload=upload_outcome,
            preview=preview,
            warnings=warnings,
        )

    return worker.run(_pipeline)


def describe_fill_result(result: FormFillResult) -> list[str]:
    """Human-readable lines describing a FormFillResult's field outcomes, upload
    outcome, missing fields, and preview — for callers to stream as progress steps
    and/or join into a summary. Excludes warnings: callers already have
    `result.warnings` directly, and those use a different message prefix
    (`[warning]`) than everything else here.
    """
    lines = []
    for outcome in result.filled_fields:
        status = "filled" if outcome.success else f"FAILED ({outcome.error})"
        label = outcome.field.label or outcome.field.selector
        lines.append(f"{label}: {status}")

    if result.upload and result.upload.attempted:
        upload_status = "uploaded" if result.upload.success else f"FAILED ({result.upload.error})"
        lines.append(f"resume upload: {upload_status}")

    if result.missing_fields:
        missing_labels = ", ".join(describe_missing_field(f) for f in result.missing_fields)
        lines.append(
            f"needs manual input: {missing_labels} — answer once via "
            "POST /user/learned-fields (key = exact field label) and it will be "
            "filled automatically on future forms"
        )

    preview_note = f" (screenshot: {result.preview.screenshot_path})" if result.preview.screenshot_path else ""
    lines.append(f"Preview ready — review before submitting{preview_note}")

    return lines


def answer_missing_fields(
    worker: BrowserWorkerProtocol,
    missing_fields: list[FieldSpec],
    reply: str,
) -> tuple[list[FillOutcome], list[FieldSpec], dict[str, str]]:
    """Matches a freeform natural-language reply against fields a prior fill_form()
    run left missing, and fills whichever ones the reply answers on the SAME live
    page fill_form() used. Returns (outcomes for fields it filled, fields still
    unanswered, a normalized_label -> answer map for the caller to persist via
    learned_fields so future forms skip asking again).

    Only safe to call while the page from the original fill_form() run is still
    open — each FieldSpec holds a live Playwright Frame reference tied to that
    page. If the page has since navigated away, filling those fields fails (each
    field fails independently and reports its own error, same as apply_field_plan
    elsewhere — this never raises for a stale frame).
    """
    if not missing_fields or not reply:
        return [], missing_fields, {}

    answers = match_reply_to_fields(reply, missing_fields)
    if not answers:
        return [], missing_fields, {}

    plans: list[FieldPlan] = []
    still_missing: list[FieldSpec] = []
    for f in missing_fields:
        answer = answers.get(f.marker_id)
        if answer:
            plans.append(FieldPlan(field=f, value=answer, source=FieldSource.PROFILE))
        else:
            still_missing.append(f)

    outcomes, _ = worker.run(lambda page: apply_field_plan(plans)) if plans else ([], [])
    learned = {normalize_label(p.field.label): p.value for p in plans if p.field.label}

    return outcomes, still_missing, learned
