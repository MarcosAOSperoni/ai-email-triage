import httpx

from app.config import settings

_SYSTEM = """\
You are drafting a reply on behalf of the user. Write a concise, professional reply.
Keep it under 150 words unless the email genuinely requires more detail.
Do not add a subject line. Do not add placeholders like [Your Name] — end naturally."""


def draft_reply(subject: str, sender: str, body: str, style_preferences: str = "") -> str:
    style_note = f"Writing style: {style_preferences}" if style_preferences else ""
    user_content = f"{style_note}\n\nOriginal email:\nFrom: {sender}\nSubject: {subject}\n\n{body}".strip()

    response = httpx.post(
        f"{settings.ollama_host}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
        },
        timeout=120.0,
    )
    response.raise_for_status()

    return response.json()["message"]["content"].strip()
