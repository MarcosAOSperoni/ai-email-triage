import base64
from datetime import datetime, timezone

from googleapiclient.discovery import build

from app.gmail.auth import get_credentials


def _extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def fetch_since(since: datetime) -> list[dict]:
    """Return emails received after `since` (UTC). Each item is a plain dict."""
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    after_ts = int(since.timestamp())
    query = f"after:{after_ts} -subject:\"Email Triage\""

    result = service.users().messages().list(userId="me", q=query, maxResults=100).execute()
    message_stubs = result.get("messages", [])

    emails = []
    for stub in message_stubs:
        msg = service.users().messages().get(userId="me", id=stub["id"], format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])

        internal_date_ms = int(msg.get("internalDate", 0))
        received_at = datetime.fromtimestamp(internal_date_ms / 1000, tz=timezone.utc)

        body = _extract_body(msg.get("payload", {}))
        # Trim to 4000 chars — enough context for the LLM without blowing the context window
        body = body.strip()[:4000]

        emails.append({
            "provider": "gmail",
            "message_id": msg["id"],
            "subject": _header(headers, "Subject"),
            "sender": _header(headers, "From"),
            "received_at": received_at,
            "body": body,
        })

    return emails
