import json

from groq import APIError

from ._llm import get_groq_client as _client_instance
from ._llm import get_text_model, parse_json_response
from .models import FieldSpec, describe_fields_for_llm

_REPLY_MATCH_SYSTEM_PROMPT = """You are matching a user's freeform natural-language
reply against a list of form fields they were asked to answer.

You will be given the still-unanswered fields (each with a marker_id, label,
field_type, and options if it's a select/radio) and the user's reply. For each
field the reply actually answers, extract a clean answer value:
- a plain string for text/textarea fields
- one of the field's given options, verbatim, for select/radio fields
- "true" or "false" for checkbox fields

Only answer fields the reply actually addresses — do not guess or invent a value
for a field the reply doesn't mention.

Output ONLY a JSON object mapping each answered marker_id to its answer string.
No markdown, no explanation. Example:
{"abc123": "LinkedIn", "def456": "true"}
"""


def match_reply_to_fields(reply: str, fields: list[FieldSpec]) -> dict[str, str]:
    """Maps a freeform reply to marker_id -> answer for whichever of the given
    fields the reply actually addresses. Fields the reply doesn't mention are
    simply absent from the result, never guessed."""
    if not reply or not fields:
        return {}

    field_descriptions = describe_fields_for_llm(fields)
    user_prompt = json.dumps({"reply": reply, "fields": field_descriptions})

    try:
        response = _client_instance().chat.completions.create(
            model=get_text_model(),
            messages=[
                {"role": "system", "content": _REPLY_MATCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        decisions = parse_json_response(response.choices[0].message.content)
    except (APIError, json.JSONDecodeError):
        return {}

    valid_marker_ids = {f.marker_id for f in fields}
    return {k: v for k, v in decisions.items() if k in valid_marker_ids and isinstance(v, str) and v}
