import asyncio
import logging
import os

from service.syncService import sync_gmail_to_sheets

logger = logging.getLogger(__name__)


def _get_sync_interval_seconds() -> int:
    raw = (os.getenv("AUTO_SYNC_INTERVAL_SECONDS") or "60").strip()
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid AUTO_SYNC_INTERVAL_SECONDS=%r, fallback to 60", raw)
        return 60
    return max(15, value)


async def auto_sync_loop():
    interval_seconds = _get_sync_interval_seconds()
    while True:
        try:
            count = sync_gmail_to_sheets()
            logger.info("[AUTO SYNC] saved %s new emails", count)
        except Exception:
            logger.exception("[AUTO SYNC ERROR]")

        await asyncio.sleep(interval_seconds)
