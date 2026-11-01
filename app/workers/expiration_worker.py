"""Background worker for automatic room expiration and media cleanup."""

import asyncio
import logging
import uuid

import app.db.session as db_session_module
from app.core.config import settings
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.deletion_repo import DeletionTaskRepository
from app.repositories.room_repo import RoomRepository
from app.services.storage_service import default_storage_service
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


async def purge_room_and_media(room_id: uuid.UUID) -> bool:
    """Safely purge all storage files and database records for a single room."""
    async with db_session_module.async_session_factory() as session:
        room_repo = RoomRepository()
        attachment_repo = AttachmentRepository()
        deletion_repo = DeletionTaskRepository()

        # 1. Close WebSockets
        await ws_manager.close_room_connections(room_id, reason="Room has expired.")

        # 2. Collect storage keys
        storage_keys = await attachment_repo.get_storage_keys_by_room(session, room_id)

        # 3. Record outbox task
        task = await deletion_repo.create(
            session=session,
            room_id=room_id,
            storage_keys=storage_keys,
            status="processing",
        )
        await session.commit()

        # 4. Attempt physical storage deletion
        deleted_count, failed_keys = await default_storage_service.delete_many(storage_keys)

        if not failed_keys:
            # Physical deletion succeeded; safely cascade delete room database row
            await deletion_repo.mark_completed(session, task.id)
            await room_repo.delete(session, room_id)
            await session.commit()
            logger.info(f"Room {room_id} and its {len(storage_keys)} files successfully purged.")
            return True
        else:
            # Storage cleanup failed; record error for retry worker
            err_msg = f"Failed to delete {len(failed_keys)} storage keys: {failed_keys}"
            logger.error(f"Room {room_id} storage purge incomplete: {err_msg}")
            await deletion_repo.mark_failed(session, task.id, error_log=err_msg)
            await session.commit()
            return False


async def run_expiration_worker(stop_event: asyncio.Event) -> None:
    """Periodic worker checking for expired rooms every interval."""
    logger.info("Room expiration worker started.")
    room_repo = RoomRepository()

    while not stop_event.is_set():
        try:
            async with db_session_module.async_session_factory() as session:
                expired_rooms = await room_repo.get_expired_rooms_for_update(session, limit=50)
                room_ids = [r.id for r in expired_rooms]
                for r in expired_rooms:
                    r.status = "deleting"
                await session.commit()

            for rid in room_ids:
                try:
                    await purge_room_and_media(rid)
                except Exception as ex:
                    logger.error(f"Error purging room {rid}: {ex}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in expiration worker loop: {e}", exc_info=True)

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.EXPIRATION_WORKER_INTERVAL_SECONDS,
            )
        except TimeoutError:
            pass

    logger.info("Room expiration worker stopped.")
