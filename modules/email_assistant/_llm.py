import json
import os

from groq import AsyncGroq

_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not set in .env")
        _client = AsyncGroq(api_key=api_key)
    return _client


def get_text_model() -> str:
    return os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")


def parse_json_response(raw: str):
    """Strip an optional ```json ... ``` code fence and parse the JSON body.

    strict=False allows literal control characters (e.g. raw newlines) inside
    JSON string values — the model is asked to escape "\\n" itself, but for
    multi-line content like a poem it sometimes emits a real newline instead,
    which strict json.loads rejects even though the content itself is fine."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw, strict=False)
