"""Participant domain service handling guest authentication and membership."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ForbiddenRoomAccessError,
    InvalidGuestTokenError,
    RoomClosedError,
    RoomExpiredError,
    RoomNotFoundError,
)
from app.core.security import hash_guest_token
from app.models.participant import Participant
from app.repositories.participant_repo import ParticipantRepository
from app.repositories.room_repo import RoomRepository
from app.schemas.participant import MemberListData, ParticipantItem


class ParticipantService:
    def __init__(
        self,
        participant_repo: ParticipantRepository | None = None,
        room_repo: RoomRepository | None = None,
    ):
        self.participant_repo = participant_repo or ParticipantRepository()
        self.room_repo = room_repo or RoomRepository()

    async def authenticate_guest(
        self,
        session: AsyncSession,
        raw_token: str,
    ) -> Participant:
        if not raw_token or not raw_token.strip():
            raise InvalidGuestTokenError("Guest token is required.")

        token_hash = hash_guest_token(raw_token.strip())
        participant = await self.participant_repo.get_by_token_hash(session, token_hash)
        if not participant:
            raise InvalidGuestTokenError("Invalid guest authorization token.")

        room = await self.room_repo.get_by_id(session, participant.room_id)
        if not room:
            raise RoomNotFoundError("The associated room does not exist.")

        now = datetime.now(UTC)
        if room.status != "active":
            raise RoomClosedError("This room is no longer active.")
        if room.expires_at <= now:
            raise RoomExpiredError("This temporary room has expired.")

        # Update last seen
        await self.participant_repo.update_last_seen(session, participant.id)

        return participant

    async def get_room_members(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        participant: Participant,
        online_participant_ids: set[uuid.UUID] | None = None,
    ) -> MemberListData:
        if participant.room_id != room_id:
            raise ForbiddenRoomAccessError()

        participants = await self.participant_repo.get_all_by_room(session, room_id)
        online_set = online_participant_ids or set()

        items = [
            ParticipantItem(
                id=p.id,
                nickname=p.nickname,
                is_host=p.is_host,
                joined_at=p.joined_at,
                last_seen_at=p.last_seen_at,
                is_online=p.id in online_set,
            )
            for p in participants
        ]

        return MemberListData(members=items, total_count=len(items))
