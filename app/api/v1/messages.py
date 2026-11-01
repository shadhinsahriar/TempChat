"""Message REST endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_participant,
    get_db_session,
    get_message_service,
)
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.models.participant import Participant
from app.schemas.common import APIResponse
from app.schemas.message import (
    MessageCreateRequest,
    MessageItem,
    MessageListData,
    MessageUpdateRequest,
    ReceiptBrief,
)
from app.services.message_service import MessageService
from app.websocket.events import evt_message_deleted, evt_message_new, evt_message_read
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/rooms/{room_id}/messages", tags=["messages"])


@router.get(
    "",
    response_model=APIResponse[MessageListData],
    summary="Get paginated room message history",
)
async def list_messages(
    room_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    message_service: MessageService = Depends(get_message_service),
) -> APIResponse[MessageListData]:
    data = await message_service.get_messages(
        session=session,
        room_id=room_id,
        participant=participant,
        limit=limit,
        offset=offset,
    )
    return APIResponse.ok(data)


@router.post(
    "",
    response_model=APIResponse[MessageItem],
    status_code=status.HTTP_201_CREATED,
    summary="Send a message in the room",
)
async def send_message(
    room_id: uuid.UUID,
    request: MessageCreateRequest,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    message_service: MessageService = Depends(get_message_service),
) -> APIResponse[MessageItem]:
    # Rate limit check per participant
    await rate_limiter.check_rate_limit(
        key=f"messages:{participant.id}",
        max_requests=settings.RATE_LIMIT_MESSAGES,
    )

    message_item = await message_service.send_message(
        session=session,
        room_id=room_id,
        sender=participant,
        type=request.type,
        content=request.content,
        reply_to_id=request.reply_to_id,
    )

    # Broadcast new message event to all active room sockets
    envelope = evt_message_new(room_id, message_item.model_dump(mode="json"))
    await ws_manager.broadcast(room_id, envelope)

    return APIResponse.ok(message_item)


@router.patch(
    "/{message_id}",
    response_model=APIResponse[MessageItem],
    summary="Edit own message",
)
async def edit_message(
    room_id: uuid.UUID,
    message_id: uuid.UUID,
    request: MessageUpdateRequest,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    message_service: MessageService = Depends(get_message_service),
) -> APIResponse[MessageItem]:
    updated_item = await message_service.edit_message(
        session=session,
        room_id=room_id,
        message_id=message_id,
        participant=participant,
        new_content=request.content,
    )
    return APIResponse.ok(updated_item)


@router.delete(
    "/{message_id}",
    response_model=APIResponse[MessageItem],
    summary="Delete own message (or host delete)",
)
async def delete_message(
    room_id: uuid.UUID,
    message_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    message_service: MessageService = Depends(get_message_service),
) -> APIResponse[MessageItem]:
    deleted_item = await message_service.delete_message(
        session=session,
        room_id=room_id,
        message_id=message_id,
        participant=participant,
    )

    # Broadcast delete event
    deleted_iso = deleted_item.deleted_at.isoformat() if deleted_item.deleted_at else ""
    await ws_manager.broadcast(
        room_id,
        evt_message_deleted(room_id, message_id, participant.id, deleted_iso),
    )

    return APIResponse.ok(deleted_item)


@router.post(
    "/{message_id}/read",
    response_model=APIResponse[ReceiptBrief],
    summary="Mark message as read",
)
async def mark_message_as_read(
    room_id: uuid.UUID,
    message_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    message_service: MessageService = Depends(get_message_service),
) -> APIResponse[ReceiptBrief]:
    receipt = await message_service.mark_read(
        session=session,
        room_id=room_id,
        message_id=message_id,
        participant=participant,
    )

    # Broadcast read receipt
    read_iso = receipt.read_at.isoformat() if receipt.read_at else ""
    await ws_manager.broadcast(
        room_id,
        evt_message_read(room_id, message_id, participant.id, read_iso),
    )

    return APIResponse.ok(receipt)
