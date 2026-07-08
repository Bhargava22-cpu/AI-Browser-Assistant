from playwright.sync_api import Page

from .detector import detect_fields
from .filler import apply_field_plan
from .generator import generate_long_text_batch
from .mapper import map_fields_to_profile
from .mapper import normalize_label
from .models import BrowserWorkerProtocol, FieldSource, FormFillResult
from .preview import build_preview
from .profile_utils import flatten_profile
from .upload import upload_resume

__all__ = ["fill_form", "normalize_label"]


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
