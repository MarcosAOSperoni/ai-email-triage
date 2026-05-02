import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Email, Preference
from app.db.session import AsyncSessionLocal
from app.gmail.fetch import fetch_since
from app.llm.classify import classify
from app.llm.draft import draft_reply
from app.summary import send_summary

log = logging.getLogger(__name__)

STATE_FILE = Path("state.json")


def _load_last_check() -> datetime:
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        return datetime.fromisoformat(data["last_check"])
    return datetime.now(tz=timezone.utc) - timedelta(hours=24)


def _save_last_check(dt: datetime) -> None:
    STATE_FILE.write_text(json.dumps({"last_check": dt.isoformat()}))


async def _load_preferences(session: AsyncSession) -> dict[str, str]:
    rows = (await session.execute(select(Preference))).scalars().all()
    prefs: dict[str, list[str]] = {}
    for p in rows:
        prefs.setdefault(p.type, []).append(p.value)
    return {k: ", ".join(v) for k, v in prefs.items()}


async def run_triage() -> None:
    now = datetime.now(tz=timezone.utc)
    last_check = _load_last_check()

    log.info("Fetching emails since %s", last_check.isoformat())
    raw_emails = fetch_since(last_check)
    log.info("Fetched %d emails", len(raw_emails))

    if not raw_emails:
        _save_last_check(now)
        return

    async with AsyncSessionLocal() as session:
        prefs = await _load_preferences(session)
        pref_str = "; ".join(f"{k}: {v}" for k, v in prefs.items()) if prefs else ""
        style_prefs = prefs.get("tone", "")

        new_emails: list[Email] = []

        for raw in raw_emails:
            existing = (
                await session.execute(
                    select(Email).where(Email.message_id == raw["message_id"])
                )
            ).scalar_one_or_none()
            if existing:
                continue

            email = Email(**raw)
            session.add(email)
            await session.flush()

            try:
                result = classify(
                    subject=email.subject,
                    sender=email.sender,
                    body=email.body,
                    preferences=pref_str,
                )
                email.classification = result["classification"]
                email.classification_reason = result["reason"]
                log.info("[%s] %s — %s", email.classification, email.sender, email.subject)
            except Exception:
                log.exception("Classification failed for message %s", email.message_id)
                email.classification = "informational"

            if email.classification == "important":
                try:
                    email.suggested_reply = draft_reply(
                        subject=email.subject,
                        sender=email.sender,
                        body=email.body,
                        style_preferences=style_prefs,
                    )
                except Exception:
                    log.exception("Draft failed for message %s", email.message_id)

            new_emails.append(email)

        await session.commit()

    new_important = [e for e in new_emails if e.classification == "important"]
    if new_emails:
        await send_summary(new_emails)

    _save_last_check(now)
    log.info("Triage complete. %d important, %d total.", len(new_important), len(new_emails))
