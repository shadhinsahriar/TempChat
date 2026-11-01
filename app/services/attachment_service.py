"""Attachment domain service orchestrating validation, storage, and retrieval."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AttachmentNotFoundError,
    ForbiddenRoomAccessError,
    RoomClosedError,
    RoomExpiredError,
)
from app.models.attachment import Attachment
from app.models.participant import Participant
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.room_repo import RoomRepository
from app.schemas.attachment import AttachmentData
from app.services.storage_service import StorageService, default_storage_service


class AttachmentService:
    def __init__(
        self,
        attachment_repo: AttachmentRepository | None = None,
        message_repo: MessageRepository | None = None,
        room_repo: RoomRepository | None = None,
        storage_service: StorageService | None = None,
    ):
        self.attachment_repo = attachment_repo or AttachmentRepository()
        self.message_repo = message_repo or MessageRepository()
        self.room_repo = room_repo or RoomRepository()
        self.storage_service = storage_service or default_storage_service

    async def upload_attachment(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        sender: Participant,
        filename: str,
        declared_mime: str,
        content: bytes,
    ) -> AttachmentData:
        if sender.room_id != room_id:
            raise ForbiddenRoomAccessError()

        # Validate active and unexpired room
        room = await self.room_repo.get_by_id(session, room_id)
        if not room or room.status != "active":
            raise RoomClosedError()
        from datetime import datetime

        if room.expires_at <= datetime.now(UTC):
            raise RoomExpiredError()

        # File validation (magic bytes, size, whitelist)
        detected_mime, media_type = self.storage_service.validate_file(
            filename=filename,
            declared_mime=declared_mime,
            content=content,
        )

        # 1. Create message for this attachment
        message = await self.message_repo.create(
            session=session,
            room_id=room_id,
            sender_id=sender.id,
            type=media_type,
            content=None,
        )

        # 2. Generate random safe storage key and save to physical store
        storage_key = self.storage_service.generate_storage_key(room_id, filename)
        await self.storage_service.save_media(
            storage_key=storage_key,
            content=content,
            mime_type=detected_mime,
        )

        # 3. Create database attachment record
        attachment = await self.attachment_repo.create(
            session=session,
            message_id=message.id,
            room_id=room_id,
            storage_key=storage_key,
            original_filename=filename,
            mime_type=detected_mime,
            size_bytes=len(content),
            media_type=media_type,
        )

        return AttachmentData(
            id=attachment.id,
            message_id=attachment.message_id,
            room_id=attachment.room_id,
            original_filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            size_bytes=attachment.size_bytes,
            media_type=attachment.media_type,
            created_at=attachment.created_at,
        )

    async def get_attachment_stream(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        attachment_id: uuid.UUID,
        participant: Participant,
    ) -> tuple[Attachment, AsyncGenerator[bytes, None]]:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()

        attachment = await self.attachment_repo.get_by_id(session, attachment_id)
        if not attachment or attachment.room_id != room_id:
            raise AttachmentNotFoundError()

        stream = self.storage_service.stream_media(attachment.storage_key)
        return attachment, stream
