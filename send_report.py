"""Email a summary of all emails currently in the DB without fetching or updating state."""
import asyncio
import logging

from sqlalchemy import select
from app.db.models import Email
from app.db.session import AsyncSessionLocal
from app.summary import send_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        emails = (await session.execute(
            select(Email).order_by(Email.received_at.desc())
        )).scalars().all()

    await send_summary(emails)


asyncio.run(main())
