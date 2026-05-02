from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_CLIENT_CONFIG = {
    "installed": {
        "client_id": settings.gmail_client_id,
        "client_secret": settings.gmail_client_secret,
        "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def get_credentials() -> Credentials:
    token_path = Path(settings.gmail_token_file)
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(_CLIENT_CONFIG, SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return creds
