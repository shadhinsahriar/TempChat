"""Attachment upload and retrieval REST endpoints."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_attachment_service,
    get_current_participant,
    get_db_session,
)
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.models.participant import Participant
from app.schemas.attachment import AttachmentData
from app.schemas.common import APIResponse
from app.services.attachment_service import AttachmentService
from app.websocket.events import evt_message_new
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/rooms/{room_id}/attachments", tags=["attachments"])


@router.post(
    "",
    response_model=APIResponse[AttachmentData],
    status_code=status.HTTP_201_CREATED,
    summary="Upload media attachment (image, audio, or document)",
)
async def upload_attachment(
    room_id: uuid.UUID,
    file: UploadFile = File(..., description="Multipart file upload"),
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    attachment_service: AttachmentService = Depends(get_attachment_service),
) -> APIResponse[AttachmentData]:
    # Rate limit check per participant
    await rate_limiter.check_rate_limit(
        key=f"uploads:{participant.id}",
        max_requests=settings.RATE_LIMIT_UPLOADS,
    )

    file_bytes = await file.read()
    filename = file.filename or "unnamed_file"
    declared_mime = file.content_type or "application/octet-stream"

    attachment_data = await attachment_service.upload_attachment(
        session=session,
        room_id=room_id,
        sender=participant,
        filename=filename,
        declared_mime=declared_mime,
        content=file_bytes,
    )

    # Broadcast container message event to WebSocket
    from app.services.message_service import MessageService

    msg_service = MessageService()
    msg = await msg_service.message_repo.get_by_id(session, attachment_data.message_id)
    if msg:
        msg_item = msg_service._to_message_item(msg)
        await ws_manager.broadcast(
            room_id,
            evt_message_new(room_id, msg_item.model_dump(mode="json")),
        )

    return APIResponse.ok(attachment_data)


@router.get(
    "/{attachment_id}",
    summary="Securely stream/download attachment media",
)
async def get_attachment(
    room_id: uuid.UUID,
    attachment_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
    session: AsyncSession = Depends(get_db_session),
    attachment_service: AttachmentService = Depends(get_attachment_service),
) -> StreamingResponse:
    attachment, stream = await attachment_service.get_attachment_stream(
        session=session,
        room_id=room_id,
        attachment_id=attachment_id,
        participant=participant,
    )

    headers = {
        "Content-Disposition": f'inline; filename="{attachment.original_filename}"',
        "Content-Length": str(attachment.size_bytes),
    }

    return StreamingResponse(
        content=stream,
        media_type=attachment.mime_type,
        headers=headers,
    )
