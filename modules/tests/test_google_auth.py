import json
from unittest.mock import MagicMock, patch

import pytest

from modules import _google_auth


def test_returns_cached_valid_token_without_reauthorizing(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"token": "abc"}))
    secret_path = tmp_path / "client_secret.json"

    mock_creds = MagicMock(valid=True)
    with patch(
        "modules._google_auth.Credentials.from_authorized_user_file", return_value=mock_creds
    ) as mock_from_file, patch("modules._google_auth.InstalledAppFlow") as mock_flow:
        creds = _google_auth.load_credentials(["scope"], secret_path, token_path)

    assert creds is mock_creds
    mock_from_file.assert_called_once()
    mock_flow.from_client_secrets_file.assert_not_called()


def test_runs_consent_flow_when_no_token_and_no_secret(tmp_path):
    token_path = tmp_path / "token.json"
    secret_path = tmp_path / "client_secret.json"  # deliberately not created

    with pytest.raises(FileNotFoundError, match="client secret"):
        _google_auth.load_credentials(["scope"], secret_path, token_path)


def test_refreshes_expired_token_with_refresh_token(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"token": "abc"}))
    secret_path = tmp_path / "client_secret.json"

    mock_creds = MagicMock(valid=False, expired=True, refresh_token="rt")
    mock_creds.to_json.return_value = json.dumps({"token": "refreshed"})
    with patch(
        "modules._google_auth.Credentials.from_authorized_user_file", return_value=mock_creds
    ), patch("modules._google_auth.Request"):
        creds = _google_auth.load_credentials(["scope"], secret_path, token_path)

    assert creds is mock_creds
    mock_creds.refresh.assert_called_once()
    assert token_path.read_text() == json.dumps({"token": "refreshed"})


def test_runs_consent_flow_and_caches_token_when_secret_present(tmp_path):
    token_path = tmp_path / "token.json"
    secret_path = tmp_path / "client_secret.json"
    secret_path.write_text("{}")

    mock_creds = MagicMock()
    mock_creds.to_json.return_value = json.dumps({"token": "new"})
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_creds
    with patch(
        "modules._google_auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow
    ) as mock_from_secrets:
        creds = _google_auth.load_credentials(["scope"], secret_path, token_path)

    assert creds is mock_creds
    mock_from_secrets.assert_called_once_with(str(secret_path), ["scope"])
    mock_flow.run_local_server.assert_called_once_with(port=0, timeout_seconds=300)
    assert token_path.read_text() == json.dumps({"token": "new"})
