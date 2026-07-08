import base64
import json
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .models import EmailDraftPlan, EmailSendResult

# Least-privilege scope — this module only ever sends, never reads the inbox.
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

CREDENTIALS_DIR = Path(__file__).resolve().parent.parent.parent / "week5" / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

_service = None


def _load_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not CLIENT_SECRET_PATH.exists():
            raise FileNotFoundError(
                f"Gmail OAuth client secret not found at {CLIENT_SECRET_PATH} — "
                "download it from Google Cloud Console and place it there"
            )
        # Opens a real browser window on this machine for the Google consent screen.
        # timeout_seconds bounds an abandoned/closed consent tab — without it the
        # loopback server (and the executor thread running it) hangs forever, which
        # then blocks `uvicorn --reload`'s graceful shutdown on process exit.
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
        creds = flow.run_local_server(port=0, timeout_seconds=300)

    TOKEN_PATH.write_text(creds.to_json())
    return creds


def get_gmail_service():
    global _service
    if _service is None:
        creds = _load_credentials()
        _service = build("gmail", "v1", credentials=creds)
    return _service


def _build_raw_message(draft: EmailDraftPlan) -> dict:
    message = MIMEText(draft.body)
    message["to"] = draft.to_email
    message["subject"] = draft.subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw}


def send_email(draft: EmailDraftPlan) -> EmailSendResult:
    try:
        service = get_gmail_service()
        sent = (
            service.users()
            .messages()
            .send(userId="me", body=_build_raw_message(draft))
            .execute()
        )
        return EmailSendResult(success=True, message_id=sent.get("id"))
    except (HttpError, FileNotFoundError, RefreshError, WSGITimeoutError, json.JSONDecodeError) as e:
        return EmailSendResult(success=False, error=str(e))
