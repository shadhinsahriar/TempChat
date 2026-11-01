"""Attachment repository for database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment


class AttachmentRepository:
    async def create(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        room_id: uuid.UUID,
        storage_key: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        media_type: str,
    ) -> Attachment:
        attachment = Attachment(
            message_id=message_id,
            room_id=room_id,
            storage_key=storage_key,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            media_type=media_type,
        )
        session.add(attachment)
        await session.flush()
        return attachment

    async def get_by_id(
        self,
        session: AsyncSession,
        attachment_id: uuid.UUID,
    ) -> Attachment | None:
        result = await session.execute(select(Attachment).where(Attachment.id == attachment_id))
        return result.scalar_one_or_none()

    async def get_storage_keys_by_room(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
    ) -> list[str]:
        result = await session.execute(
            select(Attachment.storage_key).where(Attachment.room_id == room_id)
        )
        return list(result.scalars().all())
