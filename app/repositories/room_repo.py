"""Room repository for database operations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.participant import Participant
from app.models.room import Room


class RoomRepository:
    async def get_by_id(self, session: AsyncSession, room_id: uuid.UUID) -> Room | None:
        result = await session.execute(select(Room).where(Room.id == room_id))
        return result.scalar_one_or_none()

    async def get_by_code(self, session: AsyncSession, code: str) -> Room | None:
        result = await session.execute(select(Room).where(Room.code == code))
        return result.scalar_one_or_none()

    async def is_code_taken(self, session: AsyncSession, code: str) -> bool:
        result = await session.execute(select(func.count(Room.id)).where(Room.code == code))
        return (result.scalar() or 0) > 0

    async def create(
        self,
        session: AsyncSession,
        code: str,
        room_type: str,
        expires_at: datetime,
        max_members: int,
        password_hash: str | None = None,
    ) -> Room:
        room = Room(
            code=code,
            room_type=room_type,
            expires_at=expires_at,
            max_members=max_members,
            password_hash=password_hash,
            status="active",
        )
        session.add(room)
        await session.flush()
        return room

    async def set_host(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        host_participant_id: uuid.UUID,
    ) -> None:
        await session.execute(
            update(Room).where(Room.id == room_id).values(host_participant_id=host_participant_id)
        )

    async def get_participant_count(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
    ) -> int:
        result = await session.execute(
            select(func.count(Participant.id)).where(Participant.room_id == room_id)
        )
        return result.scalar() or 0

    async def get_expired_rooms_for_update(
        self,
        session: AsyncSession,
        limit: int = 50,
    ) -> list[Room]:
        now = datetime.now(UTC)
        # Select active rooms that have expired using row-level locking
        query = (
            select(Room)
            .where(Room.status == "active", Room.expires_at <= now)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        status: str,
    ) -> None:
        await session.execute(update(Room).where(Room.id == room_id).values(status=status))

    async def delete(self, session: AsyncSession, room_id: uuid.UUID) -> None:
        await session.execute(delete(Room).where(Room.id == room_id))
