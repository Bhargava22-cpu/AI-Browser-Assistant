import json
import os

from groq import Groq

_client: Groq | None = None


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=api_key)
    return _client


def get_text_model() -> str:
    return os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")


def parse_json_response(raw: str):
    """Strip an optional ```json ... ``` code fence and parse the JSON body."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)
