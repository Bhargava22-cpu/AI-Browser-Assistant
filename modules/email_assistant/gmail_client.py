import base64
import json
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import WSGITimeoutError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .. import _google_auth
from .models import EmailDraftPlan, EmailSendResult

# Least-privilege scope — this module only ever sends, never reads the inbox.
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

CREDENTIALS_DIR = Path(__file__).resolve().parent.parent.parent / "week5" / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

_service = None


def _load_credentials() -> Credentials:
    return _google_auth.load_credentials(SCOPES, CLIENT_SECRET_PATH, TOKEN_PATH)


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
