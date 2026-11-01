"""Room management REST endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_client_ip,
    get_current_participant,
    get_db_session,
    get_participant_service,
    get_room_service,
)
from app.core.config import settings
from app.core.exceptions import ForbiddenRoomAccessError
from app.core.rate_limit import rate_limiter
from app.models.participant import Participant
from app.schemas.common import APIResponse
from app.schemas.participant import MemberListData
from app.schemas.room import (
    RoomCreatedData,
    RoomCreateRequest,
    RoomDetailData,
    RoomJoinedData,
    RoomJoinRequest,
)
from app.schemas.websocket import WSTicketResponse
from app.services.participant_service import ParticipantService
from app.services.room_service import RoomService
from app.websocket.manager import ws_manager
from app.websocket.tickets import ticket_store
from app.workers.expiration_worker import purge_room_and_media

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post(
    "",
    response_model=APIResponse[RoomCreatedData],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new temporary room",
)
async def create_room(
    request: RoomCreateRequest,
    client_ip: str = Depends(get_client_ip),
    session: AsyncSession = Depends(get_db_session),
    room_service: RoomService = Depends(get_room_service),
) -> APIResponse[RoomCreatedData]:
    # Rate limit check per IP
    await rate_limiter.check_rate_limit(
        key=f"create_room:{client_ip}",
        max_requests=settings.RATE_LIMIT_CREATE_ROOM,
    )

    created_data = await room_service.create_room(
        session=session,
        nickname=request.nickname,
        room_type=request.room_type,
        duration_minutes=request.duration_minutes,
        max_members=request.max_members,
        password=request.password,
    )
    return APIResponse.ok(created_data)


@router.post(
    "/join",
    response_model=APIResponse[RoomJoinedData],
    summary="Join an existing room using code and optional password",
)
async def join_room(
    request: RoomJoinRequest,
    client_ip: str = Depends(get_client_ip),
    session: AsyncSession = Depends(get_db_session),
    room_service: RoomService = Depends(get_room_service),
) -> APIResponse[RoomJoinedData]:
    # Rate limit check per IP
    await rate_limiter.check_rate_limit(
        key=f"join_room:{client_ip}",
        max_requests=settings.RATE_LIMIT_JOIN_ROOM,
    )

    joined_data = await room_service.join_room(
        session=session,
        code=request.code,
        nickname=request.nickname,
        password=request.password,
    )
    return APIResponse.ok(joined_data)


@router.get(
    "/{room_id}",
    response_model=APIResponse[RoomDetailData],
    summary="Get room metadata and expiration status",
)
async def get_room(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    room_service: RoomService = Depends(get_room_service),
) -> APIResponse[RoomDetailData]:
    detail = await room_service.get_room_detail(
        session=session,
        room_id=room_id,
        participant=participant,
    )
    return APIResponse.ok(detail)


@router.get(
    "/{room_id}/members",
    response_model=APIResponse[MemberListData],
    summary="List active room participants and presence",
)
async def get_members(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    participant_service: ParticipantService = Depends(get_participant_service),
) -> APIResponse[MemberListData]:
    online_ids = ws_manager.get_online_participants(room_id)
    members_data = await participant_service.get_room_members(
        session=session,
        room_id=room_id,
        participant=participant,
        online_participant_ids=online_ids,
    )
    return APIResponse.ok(members_data)


@router.post(
    "/{room_id}/leave",
    response_model=APIResponse[dict[str, str]],
    summary="Leave room",
)
async def leave_room(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    room_service: RoomService = Depends(get_room_service),
) -> APIResponse[dict[str, str]]:
    await room_service.leave_room(
        session=session,
        room_id=room_id,
        participant=participant,
    )
    return APIResponse.ok({"message": "Successfully left the room."})


@router.delete(
    "/{room_id}",
    response_model=APIResponse[dict[str, str]],
    summary="Host early closure of room (triggers immediate deletion)",
)
async def close_room(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    room_service: RoomService = Depends(get_room_service),
) -> APIResponse[dict[str, str]]:
    await room_service.close_room(
        session=session,
        room_id=room_id,
        participant=participant,
    )
    await session.commit()

    # Trigger instant purge of room and media files
    await purge_room_and_media(room_id)

    return APIResponse.ok({"message": "Room closed and permanently purged."})


@router.post(
    "/{room_id}/ws-ticket",
    response_model=APIResponse[WSTicketResponse],
    summary="Issue single-use ticket for WebSocket authentication",
)
async def create_ws_ticket(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
) -> APIResponse[WSTicketResponse]:
    if participant.room_id != room_id:
        raise ForbiddenRoomAccessError()

    ticket = await ticket_store.create_ticket(
        room_id=room_id,
        participant_id=participant.id,
    )
    return APIResponse.ok(
        WSTicketResponse(
            ticket=ticket,
            expires_in_seconds=settings.WS_TICKET_TTL_SECONDS,
        )
    )
