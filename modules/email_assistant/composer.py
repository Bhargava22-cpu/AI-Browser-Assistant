import json
import re

from groq import APIError

from ._llm import get_groq_client as _client_instance
from ._llm import get_text_model, parse_json_response
from .models import EmailDraftPlan

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_BARE_LOCAL_PART_RE = re.compile(r"^[^@\s]+$")
_DEFAULT_DOMAIN = "gmail.com"


def _normalize_recipient(to_email: str) -> str:
    """A recipient typed without a domain (e.g. "harshithsarma0406") is assumed to be
    a Gmail address, since that's the only domain this assistant currently sends to/from
    in practice — saves typing "@gmail.com" on every command."""
    to_email = (to_email or "").strip()
    if to_email and _BARE_LOCAL_PART_RE.match(to_email):
        return f"{to_email}@{_DEFAULT_DOMAIN}"
    return to_email

_COMPOSE_SYSTEM_PROMPT = """You are writing a professional email on behalf of the
sender, using their profile only for the signature (their name).

Given the sender's profile and a one-line description of what the email should
accomplish, write a complete, polite email. Ground the email only in the intent
and profile facts provided — do not invent details, commitments, meetings, or
context not present in the input. Sign off using the sender's name from the
profile. If you don't know the recipient's name, greet them with a plain "Hi,"
— never write a placeholder like "[Recipient's Name]".

Structure the email as 2-4 short paragraphs, each 1-3 complete sentences. End
each sentence with a period — never chain multiple independent clauses together
with commas ("it helped me, I am grateful, I look forward to..." is wrong; write
each as its own sentence instead). Separate paragraphs with a blank line
("\\n\\n"). Within a single paragraph, write it as one continuous line of text
— never insert a "\\n" in the middle of a sentence or paragraph. Email clients
render a single "\\n" as a hard line break, so text chopped into short lines
looks broken to the recipient, but no paragraph breaks at all looks just as
wrong. End with a sign-off word and the sender's name on their own line, e.g.
"Best,\\nArjun Mehta" — not "Best, Arjun Mehta" on one line.

If you are given a previous draft and revision feedback instead of a fresh
intent, rewrite the email to address that feedback while keeping the same
formatting rules and staying grounded in the same profile facts — do not
introduce new claims the feedback didn't ask for.

Output ONLY a JSON object with two keys, "subject" and "body". No markdown, no
explanation. Example:
{"subject": "Following up on our conversation", "body": "Hi,\\n\\nI wanted to follow up on our conversation last week about the project timeline and next steps.\\n\\nBest,\\nJane Doe"}
"""


async def compose_email(
    profile: dict,
    to_email: str,
    body_intent: str,
    subject_hint: str | None = None,
    *,
    revise_from: EmailDraftPlan | None = None,
    feedback: str | None = None,
) -> EmailDraftPlan:
    to_email = _normalize_recipient(to_email)
    if not _EMAIL_RE.match(to_email):
        raise ValueError(
            f"'{to_email}' doesn't look like an email address — group/contact-name "
            "resolution isn't built yet, so the command needs a literal recipient address "
            "(a bare username is assumed to be @gmail.com)"
        )
    if revise_from is not None:
        if not feedback:
            raise ValueError("feedback is required to revise an email")
    elif not body_intent:
        raise ValueError("body_intent is required to compose an email")

    user_payload = {"profile": profile, "intent": body_intent}
    if revise_from is not None:
        user_payload["previous_draft"] = {"subject": revise_from.subject, "body": revise_from.body}
        user_payload["revision_feedback"] = feedback
    user_prompt = json.dumps(user_payload)

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
