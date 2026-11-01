"""Message domain service handling messages, replies, edits, and receipts."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ForbiddenRoomAccessError,
    InvalidReplyError,
    MessageNotEditableError,
    MessageNotFoundError,
    RoomClosedError,
    RoomExpiredError,
)
from app.models.message import Message
from app.models.participant import Participant
from app.repositories.message_repo import MessageRepository
from app.repositories.receipt_repo import ReceiptRepository
from app.repositories.room_repo import RoomRepository
from app.schemas.message import (
    AttachmentBrief,
    MessageItem,
    MessageListData,
    ReceiptBrief,
)


class MessageService:
    def __init__(
        self,
        message_repo: MessageRepository | None = None,
        receipt_repo: ReceiptRepository | None = None,
        room_repo: RoomRepository | None = None,
    ):
        self.message_repo = message_repo or MessageRepository()
        self.receipt_repo = receipt_repo or ReceiptRepository()
        self.room_repo = room_repo or RoomRepository()

    def _to_message_item(
        self, message: Message, fallback_sender: Participant | None = None
    ) -> MessageItem:
        from sqlalchemy import inspect as sa_inspect

        insp = sa_inspect(message)

        attachments = []
        if "attachments" in insp.dict:
            attachments = [
                AttachmentBrief(
                    id=att.id,
                    original_filename=att.original_filename,
                    mime_type=att.mime_type,
                    size_bytes=att.size_bytes,
                    media_type=att.media_type,
                )
                for att in message.attachments
            ]

        receipts = []
        if "receipts" in insp.dict:
            receipts = [
                ReceiptBrief(
                    participant_id=r.participant_id,
                    delivered_at=r.delivered_at,
                    read_at=r.read_at,
                )
                for r in message.receipts
            ]

        sender_nickname = "Anonymous"
        if fallback_sender:
            sender_nickname = fallback_sender.nickname
        elif "sender" in insp.dict and message.sender:
            sender_nickname = message.sender.nickname

        return MessageItem(
            id=message.id,
            room_id=message.room_id,
            sender_id=message.sender_id,
            sender_nickname=sender_nickname,
            type=message.type,
            content=message.content,
            reply_to_id=message.reply_to_id,
            created_at=message.created_at,
            edited_at=message.edited_at,
            deleted_at=message.deleted_at,
            attachments=attachments,
            receipts=receipts,
        )

    async def send_message(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        sender: Participant,
        type: str = "text",
        content: str | None = None,
        reply_to_id: uuid.UUID | None = None,
    ) -> MessageItem:
        if sender.room_id != room_id:
            raise ForbiddenRoomAccessError()

        # Validate room is active & not expired
        room = await self.room_repo.get_by_id(session, room_id)
        if not room or room.status != "active":
            raise RoomClosedError()
        if room.expires_at <= datetime.now(UTC):
            raise RoomExpiredError()

        # Reply validation: target must belong to the exact same room
        if reply_to_id is not None:
            parent_msg = await self.message_repo.get_by_id(session, reply_to_id)
            if not parent_msg or parent_msg.room_id != room_id:
                raise InvalidReplyError("Reply target message does not exist in this room.")

        message = await self.message_repo.create(
            session=session,
            room_id=room_id,
            sender_id=sender.id,
            type=type,
            content=content,
            reply_to_id=reply_to_id,
        )
        return self._to_message_item(message, fallback_sender=sender)

    async def get_messages(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        participant: Participant,
        limit: int = 50,
        offset: int = 0,
    ) -> MessageListData:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()

        total = await self.message_repo.count_by_room(session, room_id)
        messages = await self.message_repo.get_paginated_by_room(
            session, room_id, limit=limit, offset=offset
        )

        items = [self._to_message_item(m) for m in messages]
        return MessageListData(
            messages=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(items)) < total,
        )

    async def edit_message(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        message_id: uuid.UUID,
        participant: Participant,
        new_content: str,
    ) -> MessageItem:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()

        message = await self.message_repo.get_by_id(session, message_id)
        if not message or message.room_id != room_id:
            raise MessageNotFoundError()

        if message.sender_id != participant.id:
            raise MessageNotEditableError("You can only edit your own messages.")

        if message.deleted_at is not None:
            raise MessageNotEditableError("Cannot edit a deleted message.")

        updated = await self.message_repo.update_content(session, message_id, new_content)
        return self._to_message_item(updated)

    async def delete_message(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        message_id: uuid.UUID,
        participant: Participant,
    ) -> MessageItem:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()

        message = await self.message_repo.get_by_id(session, message_id)
        if not message or message.room_id != room_id:
            raise MessageNotFoundError()

        # Author or host can delete
        if message.sender_id != participant.id and not participant.is_host:
            raise MessageNotEditableError("Only the author or host can delete this message.")

        deleted = await self.message_repo.soft_delete(session, message_id)
        return self._to_message_item(deleted)

    async def mark_read(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        message_id: uuid.UUID,
        participant: Participant,
    ) -> ReceiptBrief:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()

        message = await self.message_repo.get_by_id(session, message_id)
        if not message or message.room_id != room_id:
            raise MessageNotFoundError()

        receipt = await self.receipt_repo.mark_read(session, message_id, participant.id)
        return ReceiptBrief(
            participant_id=receipt.participant_id,
            delivered_at=receipt.delivered_at,
            read_at=receipt.read_at,
        )
