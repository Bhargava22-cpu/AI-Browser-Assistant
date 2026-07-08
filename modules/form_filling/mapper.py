import json
import re

from groq import APIError

from ._llm import get_groq_client as _client_instance
from ._llm import get_text_model, parse_json_response
from .models import FieldPlan, FieldSource, FieldSpec, FieldType, describe_fields_for_llm

# Ordered (keyword, profile_key) rules — first match wins. Checked before falling
# back to a batched LLM call, so obvious fields never cost a token.
_HEURISTIC_RULES: list[tuple[str, str]] = [
    ("email", "email"),
    ("linkedin", "linkedin"),
    ("github", "github"),
    ("phone", "phone"),
    ("mobile", "phone"),
    ("pincode", "address_pincode"),
    ("postal", "address_pincode"),
    ("zip", "address_pincode"),
    ("city", "address_city"),
    ("state", "address_state"),
    ("country", "address_country"),
    ("address", "address_full"),
    ("college", "college"),
    ("university", "college"),
    ("degree", "degree"),
    ("graduation", "graduation_year"),
    ("skill", "skills"),
    ("full name", "name"),
]

_MAPPING_SYSTEM_PROMPT = """You are mapping web form fields to a user's profile data.

You will be given a list of form fields (each with a marker_id, label, field_type, and
options if it's a select) and the list of profile keys currently available.

For EACH field, decide one of:
- {"action": "profile", "profile_key": "<one of the available profile keys>"} if the field
  clearly corresponds to a profile key.
- {"action": "generate"} if the field expects a free-text answer that should be written for
  the user (e.g. "Why do you want this role?", "Tell us about yourself", a Statement of
  Purpose, a cover-letter-style box) rather than a fact already in the profile.
- {"action": "missing"} if the field asks for something not covered by the profile and not a
  generate-style question (e.g. date of birth, gender, salary expectation).

Output ONLY a JSON object mapping each marker_id to one of the above. No markdown, no
explanation. Example:
{"abc123": {"action": "profile", "profile_key": "email"}, "def456": {"action": "generate"}}
"""


def normalize_label(label: str) -> str:
    """Canonical form used as the key for remembered answers to previously-missing
    fields — collapses internal whitespace and case so the same question asked with
    slightly different formatting still matches."""
    return re.sub(r"\s+", " ", label.strip().lower())


def _heuristic_match(field: FieldSpec) -> str | None:
    haystack = f"{field.label} {field.placeholder}".lower()
    for keyword, profile_key in _HEURISTIC_RULES:
        # Word-boundary match (with optional trailing "s" for plurals like "skill"/"skills") —
        # a plain substring check would let "state" match inside "Statement of Purpose"
        # and silently overwrite free-text fields.
        if re.search(rf"\b{re.escape(keyword)}s?\b", haystack):
            return profile_key
    return None


def map_fields_to_profile(
    fields: list[FieldSpec], profile_flat: dict, learned_fields: dict[str, str] | None = None
) -> tuple[list[FieldPlan], list[str]]:
    learned_fields = learned_fields or {}
    warnings: list[str] = []
    plans: dict[str, FieldPlan] = {}
    remaining: list[FieldSpec] = []

    for field in fields:
        if field.field_type == FieldType.FILE:
            continue  # handled by upload.py, not the mapper

        # A field the user was asked about (and answered) on a previous run — remembered
        # by exact normalized label, checked before the heuristic/LLM tiers since it's
        # the most specific signal we have.
        learned_key = normalize_label(field.label) if field.label else ""
        if learned_key and learned_key in learned_fields:
            plans[field.marker_id] = FieldPlan(
                field=field, value=learned_fields[learned_key], source=FieldSource.PROFILE
            )
            continue

        profile_key = _heuristic_match(field)
        if profile_key and profile_flat.get(profile_key):
            plans[field.marker_id] = FieldPlan(
                field=field, value=profile_flat[profile_key], source=FieldSource.PROFILE
            )
        else:
            remaining.append(field)

    if remaining:
        llm_plans, llm_warnings = _map_via_llm(remaining, profile_flat)
        plans.update(llm_plans)
        warnings.extend(llm_warnings)

    return list(plans.values()), warnings


def _map_via_llm(
    fields: list[FieldSpec], profile_flat: dict
) -> tuple[dict[str, FieldPlan], list[str]]:
    warnings: list[str] = []
    field_descriptions = describe_fields_for_llm(fields, include_required=True)
    user_prompt = json.dumps(
        {
            "available_profile_keys": list(profile_flat.keys()),
            "fields": field_descriptions,
        }
    )

    try:
        response = _client_instance().chat.completions.create(
            model=get_text_model(),
            messages=[
                {"role": "system", "content": _MAPPING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        decisions = parse_json_response(response.choices[0].message.content)
    except (APIError, json.JSONDecodeError) as e:
        warnings.append(f"LLM field mapping failed ({e}) — remaining fields marked missing")
        return (
            {f.marker_id: FieldPlan(field=f, value=None, source=FieldSource.MISSING) for f in fields},
            warnings,
        )

    plans: dict[str, FieldPlan] = {}
    by_marker = {f.marker_id: f for f in fields}
    for marker_id, field in by_marker.items():
        decision = decisions.get(marker_id, {"action": "missing"})
        action = decision.get("action", "missing")

        if action == "profile":
            profile_key = decision.get("profile_key")
            value = profile_flat.get(profile_key) if profile_key else None
            if value:
                plans[marker_id] = FieldPlan(field, value, FieldSource.PROFILE)
            else:
                plans[marker_id] = FieldPlan(field, None, FieldSource.MISSING)
        elif action == "generate":
            plans[marker_id] = FieldPlan(field, None, FieldSource.GENERATED)
        else:
            plans[marker_id] = FieldPlan(field, None, FieldSource.MISSING)

    return plans, warnings
