"""WebSocket event envelope builders."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.security import generate_event_id
from app.schemas.websocket import WSEventEnvelope


def create_envelope(
    event: str,
    room_id: uuid.UUID,
    data: dict[str, Any],
) -> WSEventEnvelope:
    return WSEventEnvelope(
        event=event,
        room_id=room_id,
        event_id=generate_event_id(),
        timestamp=datetime.now(UTC),
        data=data,
    )


def evt_room_joined(
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
    nickname: str,
    is_host: bool,
    member_count: int,
) -> WSEventEnvelope:
    return create_envelope(
        event="room.joined",
        room_id=room_id,
        data={
            "participant": {
                "id": str(participant_id),
                "nickname": nickname,
                "is_host": is_host,
            },
            "member_count": member_count,
        },
    )


def evt_room_member_left(
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
    member_count: int,
    reason: str = "disconnected",
) -> WSEventEnvelope:
    return create_envelope(
        event="room.member_left",
        room_id=room_id,
        data={
            "participant_id": str(participant_id),
            "reason": reason,
            "member_count": member_count,
        },
    )


def evt_room_members(
    room_id: uuid.UUID,
    members: list[dict[str, Any]],
) -> WSEventEnvelope:
    return create_envelope(
        event="room.members",
        room_id=room_id,
        data={"members": members, "total_count": len(members)},
    )


def evt_message_new(
    room_id: uuid.UUID,
    message_dict: dict[str, Any],
) -> WSEventEnvelope:
    return create_envelope(
        event="message.new",
        room_id=room_id,
        data=message_dict,
    )


def evt_message_delivered(
    room_id: uuid.UUID,
    message_id: uuid.UUID,
    participant_id: uuid.UUID,
    delivered_at: str,
) -> WSEventEnvelope:
    return create_envelope(
        event="message.delivered",
        room_id=room_id,
        data={
            "message_id": str(message_id),
            "participant_id": str(participant_id),
            "delivered_at": delivered_at,
        },
    )


def evt_message_read(
    room_id: uuid.UUID,
    message_id: uuid.UUID,
    participant_id: uuid.UUID,
    read_at: str,
) -> WSEventEnvelope:
    return create_envelope(
        event="message.read",
        room_id=room_id,
        data={
            "message_id": str(message_id),
            "participant_id": str(participant_id),
            "read_at": read_at,
        },
    )


def evt_message_deleted(
    room_id: uuid.UUID,
    message_id: uuid.UUID,
    participant_id: uuid.UUID,
    deleted_at: str,
) -> WSEventEnvelope:
    return create_envelope(
        event="message.deleted",
        room_id=room_id,
        data={
            "message_id": str(message_id),
            "participant_id": str(participant_id),
            "deleted_at": deleted_at,
        },
    )


def evt_typing_start(
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
    nickname: str,
) -> WSEventEnvelope:
    return create_envelope(
        event="typing.start",
        room_id=room_id,
        data={
            "participant_id": str(participant_id),
            "nickname": nickname,
        },
    )


def evt_typing_stop(
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
) -> WSEventEnvelope:
    return create_envelope(
        event="typing.stop",
        room_id=room_id,
        data={"participant_id": str(participant_id)},
    )


def evt_room_expiring(
    room_id: uuid.UUID,
    remaining_seconds: int,
) -> WSEventEnvelope:
    return create_envelope(
        event="room.expiring",
        room_id=room_id,
        data={"remaining_seconds": remaining_seconds},
    )


def evt_room_expired(
    room_id: uuid.UUID,
    reason: str = "Room has expired.",
) -> WSEventEnvelope:
    return create_envelope(
        event="room.expired",
        room_id=room_id,
        data={"reason": reason},
    )


def evt_error(
    room_id: uuid.UUID,
    code: str,
    message: str,
) -> WSEventEnvelope:
    return create_envelope(
        event="error",
        room_id=room_id,
        data={"code": code, "message": message},
    )
