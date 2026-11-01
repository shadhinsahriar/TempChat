"""Participant repository for database operations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.participant import Participant


class ParticipantRepository:
    async def create(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        nickname: str,
        token_hash: str,
        is_host: bool = False,
    ) -> Participant:
        participant = Participant(
            room_id=room_id,
            nickname=nickname,
            token_hash=token_hash,
            is_host=is_host,
        )
        session.add(participant)
        await session.flush()
        return participant

    async def get_by_id(
        self,
        session: AsyncSession,
        participant_id: uuid.UUID,
    ) -> Participant | None:
        result = await session.execute(select(Participant).where(Participant.id == participant_id))
        return result.scalar_one_or_none()

    async def get_by_token_hash(
        self,
        session: AsyncSession,
        token_hash: str,
    ) -> Participant | None:
        result = await session.execute(
            select(Participant).where(Participant.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_all_by_room(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
    ) -> list[Participant]:
        result = await session.execute(
            select(Participant)
            .where(Participant.room_id == room_id)
            .order_by(Participant.joined_at.asc())
        )
        return list(result.scalars().all())

    async def update_last_seen(
        self,
        session: AsyncSession,
        participant_id: uuid.UUID,
    ) -> None:
        now = datetime.now(UTC)
        await session.execute(
            update(Participant).where(Participant.id == participant_id).values(last_seen_at=now)
        )

    async def delete(
        self,
        session: AsyncSession,
        participant_id: uuid.UUID,
    ) -> None:
        await session.execute(delete(Participant).where(Participant.id == participant_id))
