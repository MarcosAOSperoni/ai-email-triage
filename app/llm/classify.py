import json

import httpx

from app.config import settings

_SYSTEM = """\
You are an email triage assistant. Classify the email as one of:
- important (requires action or a response — includes expiring tokens, SSL renewals, account alerts, security notices, payment issues, deadlines, "action required" emails, offers requiring a decision, and anything time-sensitive)
- informational (good to know, no action needed — receipts, confirmations, shipping updates)
- newsletter (bulk or marketing content — promotions, sales, product updates)
- spam (junk, no action needed)

When in doubt between important and informational, choose important.

Respond ONLY with valid JSON in this exact format:
{"classification": "<label>", "reason": "<one sentence>"}"""


def classify(subject: str, sender: str, body: str, preferences: str = "") -> dict:
    user_content = f"User preferences: {preferences or 'none'}\n\nFrom: {sender}\nSubject: {subject}\n\n{body}"

    response = httpx.post(
        f"{settings.ollama_host}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content},
            ],
            "format": "json",
            "stream": False,
        },
        timeout=120.0,
    )
    response.raise_for_status()

    content = response.json()["message"]["content"]
    parsed = json.loads(content)

    label = parsed.get("classification", "informational").lower()
    if label not in {"important", "informational", "newsletter", "spam"}:
        label = "informational"

    return {"classification": label, "reason": parsed.get("reason", "")}
