"""Re-classify all emails in the DB using the current prompt and preferences."""
import asyncio
import logging

from sqlalchemy import select
from app.db.models import Email, Preference
from app.db.session import AsyncSessionLocal
from app.llm.classify import classify
from app.llm.draft import draft_reply

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
log = logging.getLogger(__name__)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        prefs = (await session.execute(select(Preference))).scalars().all()
        pref_str = "; ".join(f"{p.type}: {p.value}" for p in prefs) if prefs else ""
        style_prefs = next((p.value for p in prefs if p.type == "tone"), "")

        emails = (await session.execute(select(Email))).scalars().all()
        log.info("Re-triaging %d emails...", len(emails))

        for email in emails:
            try:
                result = classify(
                    subject=email.subject,
                    sender=email.sender,
                    body=email.body,
                    preferences=pref_str,
                )
                old = email.classification
                email.classification = result["classification"]
                email.classification_reason = result["reason"]

                if old != email.classification:
                    log.info("[%s → %s] %s | %s", old, email.classification, email.sender, email.subject)
                else:
                    log.info("[%s] %s | %s", email.classification, email.sender, email.subject)

                if email.classification == "action" and not email.suggested_reply:
                    email.suggested_reply = draft_reply(
                        subject=email.subject,
                        sender=email.sender,
                        body=email.body,
                        style_preferences=style_prefs,
                    )
            except Exception:
                log.exception("Failed for %s", email.message_id)

        await session.commit()
        log.info("Done.")


asyncio.run(main())
