"""Room domain service orchestrating creation, joining, and lifecycle rules."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ForbiddenRoomAccessError,
    InvalidRoomPasswordError,
    NotHostError,
    PasswordRequiredError,
    RoomClosedError,
    RoomExpiredError,
    RoomFullError,
    RoomNotFoundError,
)
from app.core.security import (
    generate_guest_token,
    generate_invite_code,
    hash_guest_token,
    hash_password,
    verify_password,
)
from app.models.participant import Participant
from app.models.room import Room
from app.repositories.participant_repo import ParticipantRepository
from app.repositories.room_repo import RoomRepository
from app.schemas.room import (
    ParticipantBrief,
    RoomCreatedData,
    RoomDetailData,
    RoomInfo,
    RoomJoinedData,
)


class RoomService:
    def __init__(
        self,
        room_repo: RoomRepository | None = None,
        participant_repo: ParticipantRepository | None = None,
    ):
        self.room_repo = room_repo or RoomRepository()
        self.participant_repo = participant_repo or ParticipantRepository()

    def _validate_duration(self, duration_minutes: int) -> int:
        if (
            duration_minutes < settings.MIN_ROOM_DURATION_MINUTES
            or duration_minutes > settings.MAX_ROOM_DURATION_MINUTES
        ):
            raise ValueError(
                f"Duration must be between {settings.MIN_ROOM_DURATION_MINUTES} and "
                f"{settings.MAX_ROOM_DURATION_MINUTES} minutes."
            )
        return duration_minutes

    def _validate_max_members(self, room_type: str, requested_members: int | None) -> int:
        if room_type == "private":
            return 2
        if requested_members is None:
            return settings.DEFAULT_MAX_MEMBERS_GROUP
        if requested_members < 2 or requested_members > settings.MAX_MEMBERS_GROUP_LIMIT:
            raise ValueError(
                f"Group room member limit must be between 2 and {settings.MAX_MEMBERS_GROUP_LIMIT}."
            )
        return requested_members

    async def _generate_unique_code(self, session: AsyncSession) -> str:
        for _ in range(10):
            code = generate_invite_code(6)
            if not await self.room_repo.is_code_taken(session, code):
                return code
        # Fallback to longer code on collision
        return generate_invite_code(8)

    async def create_room(
        self,
        session: AsyncSession,
        nickname: str,
        room_type: str = "group",
        duration_minutes: int = 60,
        max_members: int | None = None,
        password: str | None = None,
    ) -> RoomCreatedData:
        validated_duration = self._validate_duration(duration_minutes)
        validated_members = self._validate_max_members(room_type, max_members)

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=validated_duration)
        code = await self._generate_unique_code(session)

        pwd_hash = hash_password(password) if password else None

        room = await self.room_repo.create(
            session=session,
            code=code,
            room_type=room_type,
            expires_at=expires_at,
            max_members=validated_members,
            password_hash=pwd_hash,
        )

        raw_guest_token = generate_guest_token()
        token_hash = hash_guest_token(raw_guest_token)

        host = await self.participant_repo.create(
            session=session,
            room_id=room.id,
            nickname=nickname,
            token_hash=token_hash,
            is_host=True,
        )

        await self.room_repo.set_host(session, room.id, host.id)

        return RoomCreatedData(
            room=RoomInfo(
                id=room.id,
                code=room.code,
                invite_url=f"/join/{room.code}",
                room_type=room.room_type,
                expires_at=room.expires_at,
                max_members=room.max_members,
            ),
            participant=ParticipantBrief(
                id=host.id,
                nickname=host.nickname,
                is_host=True,
            ),
            guest_token=raw_guest_token,
        )

    async def join_room(
        self,
        session: AsyncSession,
        code: str,
        nickname: str,
        password: str | None = None,
    ) -> RoomJoinedData:
        room = await self.room_repo.get_by_code(session, code)
        if not room:
            raise RoomNotFoundError(f"Room with code '{code}' not found.")

        now = datetime.now(UTC)
        if room.status != "active":
            raise RoomClosedError("This room is no longer active.")
        if room.expires_at <= now:
            raise RoomExpiredError("This temporary room has expired.")

        # Password check
        if room.password_hash:
            if not password:
                raise PasswordRequiredError()
            if not verify_password(password, room.password_hash):
                raise InvalidRoomPasswordError()

        # Capacity check
        current_members = await self.room_repo.get_participant_count(session, room.id)
        if current_members >= room.max_members:
            raise RoomFullError()

        raw_guest_token = generate_guest_token()
        token_hash = hash_guest_token(raw_guest_token)

        participant = await self.participant_repo.create(
            session=session,
            room_id=room.id,
            nickname=nickname,
            token_hash=token_hash,
            is_host=False,
        )

        return RoomJoinedData(
            room=RoomInfo(
                id=room.id,
                code=room.code,
                invite_url=f"/join/{room.code}",
                room_type=room.room_type,
                expires_at=room.expires_at,
                max_members=room.max_members,
            ),
            participant=ParticipantBrief(
                id=participant.id,
                nickname=participant.nickname,
                is_host=False,
            ),
            guest_token=raw_guest_token,
        )

    async def get_room_detail(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        participant: Participant,
    ) -> RoomDetailData:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()

        room = await self.room_repo.get_by_id(session, room_id)
        if not room:
            raise RoomNotFoundError()

        now = datetime.now(UTC)
        if room.status != "active":
            raise RoomClosedError()
        if room.expires_at <= now:
            raise RoomExpiredError()

        member_count = await self.room_repo.get_participant_count(session, room.id)

        return RoomDetailData(
            id=room.id,
            code=room.code,
            invite_url=f"/join/{room.code}",
            room_type=room.room_type,
            expires_at=room.expires_at,
            max_members=room.max_members,
            member_count=member_count,
            is_password_protected=bool(room.password_hash),
            status=room.status,
        )

    async def leave_room(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        participant: Participant,
    ) -> None:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()

        await self.participant_repo.delete(session, participant.id)

    async def close_room(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        participant: Participant,
    ) -> Room:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()
        if not participant.is_host:
            raise NotHostError()

        room = await self.room_repo.get_by_id(session, room_id)
        if not room:
            raise RoomNotFoundError()

        # Mark room as deleting so it triggers immediate cleanup
        await self.room_repo.update_status(session, room.id, "deleting")
        return room
