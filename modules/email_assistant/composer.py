import json
import re

from groq import APIError

from ._llm import get_groq_client as _client_instance
from ._llm import get_text_model, parse_json_response
from .models import EmailDraftPlan

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_COMPOSE_SYSTEM_PROMPT = """You are writing a professional email on behalf of the
sender, using their profile only for the signature (their name).

Given the sender's profile and a one-line description of what the email should
accomplish, write a complete, polite email. Ground the email only in the intent
and profile facts provided — do not invent details, commitments, meetings, or
context not present in the input. Sign off using the sender's name from the
profile.

Output ONLY a JSON object with two keys, "subject" and "body". No markdown, no
explanation. Example:
{"subject": "Following up on our conversation", "body": "Hi,\\n\\nI wanted to follow up on...\\n\\nBest,\\nJane Doe"}
"""


async def compose_email(
    profile: dict,
    to_email: str,
    body_intent: str,
    subject_hint: str | None = None,
) -> EmailDraftPlan:
    if not _EMAIL_RE.match(to_email or ""):
        raise ValueError(
            f"'{to_email}' doesn't look like an email address — group/contact-name "
            "resolution isn't built yet, so the command needs a literal recipient address"
        )
    if not body_intent:
        raise ValueError("body_intent is required to compose an email")

    user_prompt = json.dumps({"profile": profile, "intent": body_intent})

    try:
        response = await _client_instance().chat.completions.create(
            model=get_text_model(),
            messages=[
                {"role": "system", "content": _COMPOSE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
        )
        drafted = parse_json_response(response.choices[0].message.content)
    except (APIError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to compose email: {e}") from e

    subject = subject_hint or drafted.get("subject") or "(no subject)"
    body = drafted.get("body", "")
    if not body:
        raise ValueError("LLM returned an empty email body")

    return EmailDraftPlan(to_email=to_email, subject=subject, body=body)
