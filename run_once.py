"""Run a single triage pass immediately — useful for testing."""
import asyncio
import logging

from app.db.models import Base
from app.db.session import engine
from app.pipeline import run_triage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_triage()


asyncio.run(main())
