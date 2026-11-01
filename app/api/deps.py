"""FastAPI dependency injection providers."""

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidGuestTokenError
from app.db.session import get_db_session
from app.models.participant import Participant
from app.services.attachment_service import AttachmentService
from app.services.message_service import MessageService
from app.services.participant_service import ParticipantService
from app.services.room_service import RoomService


def get_client_ip(request: Request) -> str:
    """Extract client IP address for rate limiting."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def get_current_participant(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> Participant:
    """Validate Bearer guest token and return authenticated participant."""
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidGuestTokenError("Bearer guest token required.")

    raw_token = authorization.removeprefix("Bearer ").strip()
    participant_service = ParticipantService()
    return await participant_service.authenticate_guest(session, raw_token)


def get_room_service() -> RoomService:
    return RoomService()


def get_participant_service() -> ParticipantService:
    return ParticipantService()


def get_message_service() -> MessageService:
    return MessageService()


def get_attachment_service() -> AttachmentService:
    return AttachmentService()
