import json

from groq import APIError

from ._llm import get_groq_client as _client_instance
from ._llm import get_text_model, parse_json_response
from .models import FieldSpec

_GENERATION_SYSTEM_PROMPT = """You are writing free-text answers for a job/internship
application form on behalf of a candidate, using their profile as context.

You will be given the candidate's profile and a list of form fields (marker_id + label)
that each need a written answer (e.g. "Why do you want this role?", a short Statement of
Purpose, "Tell us about yourself").

Write a concise, genuine-sounding answer (2-5 sentences) for EACH field, grounded only in
the profile facts provided — do not invent employers, projects, or credentials not present
in the profile.

Output ONLY a JSON object mapping each marker_id to its answer string. No markdown, no
explanation. Example:
{"abc123": "I'm a Computer Science graduate from IIT Bombay with hands-on experience in
Python and React, and I'm excited to apply my skills to a real engineering team."}
"""


def generate_long_text_batch(
    fields: list[FieldSpec], profile_flat: dict
) -> tuple[dict[str, str], list[str]]:
    if not fields:
        return {}, []

    warnings: list[str] = []
    field_descriptions = [{"marker_id": f.marker_id, "label": f.label} for f in fields]
    user_prompt = json.dumps({"profile": profile_flat, "fields": field_descriptions})

    try:
        response = _client_instance().chat.completions.create(
            model=get_text_model(),
            messages=[
                {"role": "system", "content": _GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
        )
        answers = parse_json_response(response.choices[0].message.content)
    except (APIError, json.JSONDecodeError) as e:
        warnings.append(f"LLM long-text generation failed ({e}) — those fields marked missing")
        return {}, warnings

    valid_marker_ids = {f.marker_id for f in fields}
    answers = {k: v for k, v in answers.items() if k in valid_marker_ids and isinstance(v, str)}
    return answers, warnings
