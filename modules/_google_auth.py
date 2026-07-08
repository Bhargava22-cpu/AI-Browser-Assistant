from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


def load_credentials(scopes: list[str], client_secret_path: Path, token_path: Path) -> Credentials:
    """Shared OAuth loading flow for Google API clients (Gmail, Calendar, ...): return
    a cached token if still valid, refresh it if expired, or run the local consent
    flow and cache the result. Callers keep their own scopes and token file for least
    privilege and independent credential lifecycles — only this mechanism is shared.
    """
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not client_secret_path.exists():
            raise FileNotFoundError(
                f"Google OAuth client secret not found at {client_secret_path} — "
                "download it from Google Cloud Console and place it there"
            )
        # Opens a real browser window on this machine for the Google consent screen.
        # timeout_seconds bounds an abandoned/closed consent tab — without it the
        # loopback server (and the executor thread running it) hangs forever, which
        # then blocks `uvicorn --reload`'s graceful shutdown on process exit.
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes)
        creds = flow.run_local_server(port=0, timeout_seconds=300)

    token_path.write_text(creds.to_json())
    return creds
