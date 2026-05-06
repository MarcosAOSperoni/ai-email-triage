import json

import httpx

from app.config import settings

_SYSTEM = """\
You are an email triage assistant. Classify the email as one of:
- action (requires a personal reply or direct action — emails from real people asking questions, meeting requests, expiring tokens, SSL renewals, payment due notices, lease/housing notices, anything that needs a human response)
- important (important to know but no reply needed — receipts, payment confirmations, security alerts, reservation confirmations, shipping updates, account notifications)
- informational (low priority, good to know — general updates, non-urgent announcements)
- newsletter (bulk or marketing content — promotions, sales, product updates, review requests, marketplace offers, deal emails)
- spam (junk, no action needed)

When in doubt between action and important, ask: does the user need to personally write back or take direct action? If yes → action. If it is just worth knowing → important.
Product review requests, eBay/marketplace deal alerts, and promotional offers are always newsletter even if they mention a specific item.

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
    if label not in {"action", "important", "informational", "newsletter", "spam"}:
        label = "informational"

    return {"classification": label, "reason": parsed.get("reason", "")}
