"""Seed the preferences table with known-important senders and topics."""
import asyncio
import logging

from sqlalchemy import delete
from app.db.models import Base, Preference
from app.db.session import AsyncSessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
log = logging.getLogger(__name__)

SENDER_PREFS = [
    # Infrastructure / security — always action required
    "github.com",
    "cloudflare.com",
    "notify.cloudflare.com",
    # Financial
    "venmo.com",
    "splitwise.com",
    "schwab.com",
    "capitalone.com",
    # Housing
    "hubatlanta",
    "emailrelay.com",
    # Identity / accounts
    "google.com",
    "anthropic.com",
    # People — always action
    "sando.law",
]

TOPIC_PREFS = [
    "action required",
    "expires",
    "expiring",
    "ssl certificate",
    "access token",
    "security alert",
    "payment due",
    "rent due",
    "domain",
    "account suspended",
    "verify",
    "invoice",
]


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Preference))

        for sender in SENDER_PREFS:
            session.add(Preference(type="sender", value=sender, weight=2.0))
            log.info("  sender: %s", sender)

        for topic in TOPIC_PREFS:
            session.add(Preference(type="topic", value=topic, weight=1.5))
            log.info("  topic: %s", topic)

        await session.commit()

    log.info("Seeded %d sender + %d topic preferences.", len(SENDER_PREFS), len(TOPIC_PREFS))


asyncio.run(main())
