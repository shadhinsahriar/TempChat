"""Message repository for database operations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.message import Message


class MessageRepository:
    async def create(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        sender_id: uuid.UUID,
        type: str,
        content: str | None = None,
        reply_to_id: uuid.UUID | None = None,
    ) -> Message:
        message = Message(
            room_id=room_id,
            sender_id=sender_id,
            type=type,
            content=content,
            reply_to_id=reply_to_id,
        )
        session.add(message)
        await session.flush()
        return message

    async def get_by_id(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
    ) -> Message | None:
        result = await session.execute(
            select(Message)
            .where(Message.id == message_id)
            .options(
                selectinload(Message.sender),
                selectinload(Message.attachments),
                selectinload(Message.receipts),
            )
        )
        return result.scalar_one_or_none()

    async def get_paginated_by_room(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        query = (
            select(Message)
            .where(Message.room_id == room_id)
            .options(
                selectinload(Message.sender),
                selectinload(Message.attachments),
                selectinload(Message.receipts),
            )
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def count_by_room(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
    ) -> int:
        result = await session.execute(
            select(func.count(Message.id)).where(Message.room_id == room_id)
        )
        return result.scalar() or 0

    async def update_content(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        new_content: str,
    ) -> Message | None:
        now = datetime.now(UTC)
        await session.execute(
            update(Message)
            .where(Message.id == message_id)
            .values(content=new_content, edited_at=now)
        )
        return await self.get_by_id(session, message_id)

    async def soft_delete(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
    ) -> Message | None:
        now = datetime.now(UTC)
        await session.execute(
            update(Message).where(Message.id == message_id).values(content=None, deleted_at=now)
        )
        return await self.get_by_id(session, message_id)
