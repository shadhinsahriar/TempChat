"""Receipt repository for tracking message delivery and read status."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt import MessageReceipt


class ReceiptRepository:
    async def get_or_create(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> MessageReceipt:
        result = await session.execute(
            select(MessageReceipt).where(
                MessageReceipt.message_id == message_id,
                MessageReceipt.participant_id == participant_id,
            )
        )
        receipt = result.scalar_one_or_none()
        if not receipt:
            receipt = MessageReceipt(
                message_id=message_id,
                participant_id=participant_id,
            )
            session.add(receipt)
            await session.flush()
        return receipt

    async def mark_delivered(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> MessageReceipt:
        receipt = await self.get_or_create(session, message_id, participant_id)
        if receipt.delivered_at is None:
            now = datetime.now(UTC)
            receipt.delivered_at = now
            await session.flush()
        return receipt

    async def mark_read(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> MessageReceipt:
        receipt = await self.get_or_create(session, message_id, participant_id)
        now = datetime.now(UTC)
        if receipt.delivered_at is None:
            receipt.delivered_at = now
        if receipt.read_at is None:
            receipt.read_at = now
        await session.flush()
        return receipt
