from pathlib import Path

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import WSGITimeoutError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .. import _google_auth
from .models import EventPlan, EventResult

# Least-privilege scope — this module only ever creates/manages events it makes,
# never reads the rest of the calendar.
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

CREDENTIALS_DIR = Path(__file__).resolve().parent.parent.parent / "week5" / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
# Separate token file from Gmail's — independent scope, independent credential
# lifecycle, so revoking/rotating one never touches the other.
TOKEN_PATH = CREDENTIALS_DIR / "token_calendar.json"

_service = None


def _load_credentials() -> Credentials:
    return _google_auth.load_credentials(SCOPES, CLIENT_SECRET_PATH, TOKEN_PATH)


def get_calendar_service():
    global _service
    if _service is None:
        creds = _load_credentials()
        _service = build("calendar", "v3", credentials=creds)
    return _service


def _build_event_body(plan: EventPlan) -> dict:
    body = {
        "summary": plan.title,
        "description": plan.description,
        "start": {"dateTime": plan.start, "timeZone": plan.timezone},
        "end": {"dateTime": plan.end, "timeZone": plan.timezone},
    }
    if plan.recurrence:
        body["recurrence"] = [plan.recurrence]
    if plan.attendees:
        body["attendees"] = [{"email": a} for a in plan.attendees]
    return body


def create_event(plan: EventPlan) -> EventResult:
    try:
        service = get_calendar_service()
        send_updates = "all" if plan.attendees else "none"
        created = (
            service.events()
            .insert(calendarId="primary", body=_build_event_body(plan), sendUpdates=send_updates)
            .execute()
        )
        return EventResult(success=True, event_id=created.get("id"), html_link=created.get("htmlLink"))
    except (HttpError, FileNotFoundError, RefreshError, WSGITimeoutError) as e:
        return EventResult(success=False, error=str(e))
