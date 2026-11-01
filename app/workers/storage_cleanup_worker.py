"""Background worker retrying failed storage deletion tasks from the outbox."""

import asyncio
import logging

import app.db.session as db_session_module
from app.core.config import settings
from app.repositories.deletion_repo import DeletionTaskRepository
from app.repositories.room_repo import RoomRepository
from app.services.storage_service import default_storage_service

logger = logging.getLogger(__name__)


async def run_storage_cleanup_worker(stop_event: asyncio.Event) -> None:
    """Periodic worker retrying orphaned file deletions."""
    logger.info("Storage cleanup outbox worker started.")
    deletion_repo = DeletionTaskRepository()
    room_repo = RoomRepository()

    while not stop_event.is_set():
        try:
            async with db_session_module.async_session_factory() as session:
                tasks = await deletion_repo.get_retryable_tasks(session, limit=50)

                for task in tasks:
                    deleted_count, failed_keys = await default_storage_service.delete_many(
                        task.storage_keys
                    )
                    if not failed_keys:
                        await deletion_repo.mark_completed(session, task.id)
                        await room_repo.delete(session, task.room_id)
                        logger.info(f"Outbox task {task.id} successfully completed.")
                    else:
                        err_msg = f"Retry failed for keys: {failed_keys}"
                        await deletion_repo.mark_failed(session, task.id, error_log=err_msg)

                await session.commit()

        except Exception as e:
            logger.error(f"Error in storage cleanup loop: {e}", exc_info=True)

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.STORAGE_CLEANUP_INTERVAL_SECONDS,
            )
        except TimeoutError:
            pass

    logger.info("Storage cleanup outbox worker stopped.")
