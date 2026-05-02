import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.db.models import Base
from app.db.session import engine
from app.pipeline import run_triage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database ready")


async def main() -> None:
    await init_db()

    scheduler = AsyncIOScheduler()

    for hour, minute in settings.schedule_times_list:
        scheduler.add_job(
            run_triage,
            CronTrigger(hour=hour, minute=minute),
            id=f"triage_{hour:02d}{minute:02d}",
            max_instances=1,
            misfire_grace_time=300,
        )
        log.info("Scheduled triage at %02d:%02d", hour, minute)

    scheduler.start()
    log.info("Scheduler running. Press Ctrl+C to stop.")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
