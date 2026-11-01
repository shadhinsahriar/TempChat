"""Domain exceptions and API error response structures."""

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse


class TempChatException(Exception):
    """Base exception for all TempChat domain errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details

    def to_json_response(self) -> JSONResponse:
        error_payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            error_payload["details"] = self.details

        return JSONResponse(
            status_code=self.status_code,
            content={
                "success": False,
                "data": None,
                "error": error_payload,
            },
        )


class RoomNotFoundError(TempChatException):
    def __init__(self, message: str = "Room not found."):
        super().__init__(
            code="ROOM_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class RoomExpiredError(TempChatException):
    def __init__(self, message: str = "This temporary room has expired."):
        super().__init__(
            code="ROOM_EXPIRED",
            message=message,
            status_code=status.HTTP_410_GONE,
        )


class RoomClosedError(TempChatException):
    def __init__(self, message: str = "This room has been closed by the host."):
        super().__init__(
            code="ROOM_CLOSED",
            message=message,
            status_code=status.HTTP_410_GONE,
        )


class RoomFullError(TempChatException):
    def __init__(self, message: str = "This room has reached its maximum member limit."):
        super().__init__(
            code="ROOM_FULL",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class InvalidRoomPasswordError(TempChatException):
    def __init__(self, message: str = "Invalid room password."):
        super().__init__(
            code="INVALID_PASSWORD",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class PasswordRequiredError(TempChatException):
    def __init__(self, message: str = "A password is required to join this room."):
        super().__init__(
            code="PASSWORD_REQUIRED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class InvalidGuestTokenError(TempChatException):
    def __init__(self, message: str = "Invalid or expired guest authorization token."):
        super().__init__(
            code="INVALID_GUEST_TOKEN",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenRoomAccessError(TempChatException):
    def __init__(self, message: str = "You do not have permission to access this room."):
        super().__init__(
            code="FORBIDDEN_ROOM_ACCESS",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotHostError(TempChatException):
    def __init__(self, message: str = "Only the room host can perform this action."):
        super().__init__(
            code="NOT_HOST",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class MessageNotFoundError(TempChatException):
    def __init__(self, message: str = "Message not found."):
        super().__init__(
            code="MESSAGE_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InvalidReplyError(TempChatException):
    def __init__(self, message: str = "Reply target must belong to the same active room."):
        super().__init__(
            code="INVALID_REPLY_TARGET",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class MessageNotEditableError(TempChatException):
    def __init__(self, message: str = "You can only edit or delete your own messages."):
        super().__init__(
            code="MESSAGE_NOT_EDITABLE",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class InvalidAttachmentError(TempChatException):
    def __init__(self, message: str):
        super().__init__(
            code="INVALID_ATTACHMENT",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class AttachmentNotFoundError(TempChatException):
    def __init__(self, message: str = "Attachment not found."):
        super().__init__(
            code="ATTACHMENT_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class RateLimitExceededError(TempChatException):
    def __init__(self, message: str = "Rate limit exceeded. Please slow down."):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
