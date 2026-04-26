import asyncio
from service.syncService import sync_gmail_to_sheets

async def auto_sync_loop():
    while True:
        try:
            # Run sync in a worker thread so blocking I/O doesn't freeze FastAPI requests.
            count = await asyncio.to_thread(sync_gmail_to_sheets)
            print(f"[AUTO SYNC] saved {count} new emails")
        except Exception as e:
            print(f"[AUTO SYNC ERROR] {e}")

        await asyncio.sleep(60)
