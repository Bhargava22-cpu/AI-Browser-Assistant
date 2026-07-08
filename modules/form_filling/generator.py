import json

from groq import APIError

from ._llm import get_groq_client as _client_instance
from ._llm import get_text_model, parse_json_response
from .models import FieldSpec

_GENERATION_SYSTEM_PROMPT = """You are writing free-text answers for fields on a web form,
on behalf of the person described by the profile below.

You will be given that person's profile and a list of form fields (marker_id + label). Each
field's label tells you what question that specific field is actually asking (e.g. "Why do
you want this role?", "Tell us about yourself", "What's your favorite hobby?", "Describe
your experience with X") — the form could be a job application, a survey, a signup form, or
anything else. Answer what the label asks, using only the register/topic implied by that
label — do not default to job-application phrasing (e.g. "excited to apply my skills") for a
field that isn't asking about a job.

Write a concise, genuine-sounding answer (1-5 sentences) for EACH field, grounded only in
the profile facts provided — do not invent employers, projects, credentials, or opinions not
present in the profile. If the profile has no facts relevant to what a field is asking,
write the shortest reasonable generic answer rather than fabricating specifics.

Output ONLY a JSON object mapping each marker_id to its answer string. No markdown, no
explanation. Example:
{"abc123": "I'm a Computer Science graduate from IIT Bombay with hands-on experience in
Python and React."}
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
