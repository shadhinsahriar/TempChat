"""WebSocket endpoint handling tickets, client events, and bi-directional messaging."""

import json
import uuid
from datetime import UTC
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

import app.db.session as db_session_module
from app.core.config import settings
from app.repositories.participant_repo import ParticipantRepository
from app.repositories.receipt_repo import ReceiptRepository
from app.repositories.room_repo import RoomRepository
from app.services.message_service import MessageService
from app.websocket.events import (
    evt_error,
    evt_message_delivered,
    evt_message_new,
    evt_message_read,
    evt_room_joined,
    evt_room_member_left,
    evt_room_members,
    evt_typing_start,
    evt_typing_stop,
)
from app.websocket.manager import ws_manager
from app.websocket.tickets import ticket_store

ws_router = APIRouter()


@ws_router.websocket("/rooms/{room_id}")
async def websocket_room_endpoint(
    websocket: WebSocket,
    room_id: uuid.UUID,
    ticket: str = Query(..., description="Single-use short-lived WebSocket ticket"),
):
    # 1. Ticket validation and atomic consumption
    participant_id = await ticket_store.consume_ticket(ticket, room_id)
    if not participant_id:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid, expired, or previously used ticket.",
        )
        return

    # 2. Database validation of room & participant status
    async with db_session_module.async_session_factory() as session:
        room_repo = RoomRepository()
        participant_repo = ParticipantRepository()

        room = await room_repo.get_by_id(session, room_id)
        participant = await participant_repo.get_by_id(session, participant_id)

        from datetime import datetime

        now = datetime.now(UTC)
        if not room or room.status != "active" or room.expires_at <= now or not participant:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Room is expired or inactive.",
            )
            return

        participant_nickname = participant.nickname
        participant_is_host = participant.is_host
        member_count = await room_repo.get_participant_count(session, room_id)
        all_participants = await participant_repo.get_all_by_room(session, room_id)

    # 3. Accept socket and register
    await websocket.accept()
    is_first_connection = await ws_manager.connect(room_id, participant_id, websocket)

    try:
        # Broadcast room.joined if this is a newly connected member
        if is_first_connection:
            join_envelope = evt_room_joined(
                room_id=room_id,
                participant_id=participant_id,
                nickname=participant_nickname,
                is_host=participant_is_host,
                member_count=member_count,
            )
            await ws_manager.broadcast(room_id, join_envelope)

        # Send initial members roster to the newly connected socket
        online_ids = ws_manager.get_online_participants(room_id)
        roster_data = [
            {
                "id": str(p.id),
                "nickname": p.nickname,
                "is_host": p.is_host,
                "is_online": p.id in online_ids,
            }
            for p in all_participants
        ]
        await ws_manager.send_personal(
            room_id, participant_id, evt_room_members(room_id, roster_data)
        )

        # 4. Inbound event loop
        message_service = MessageService()
        receipt_repo = ReceiptRepository()

        while True:
            raw_text = await websocket.receive_text()
            if len(raw_text) > settings.WS_MAX_MESSAGE_SIZE:
                await ws_manager.send_personal(
                    room_id,
                    participant_id,
                    evt_error(
                        room_id, "MESSAGE_TOO_LARGE", "WebSocket message size limit exceeded."
                    ),
                )
                continue

            try:
                payload = json.loads(raw_text)
                event_name = payload.get("event")
                data: dict[str, Any] = payload.get("data", {})
            except Exception:
                await ws_manager.send_personal(
                    room_id,
                    participant_id,
                    evt_error(room_id, "INVALID_JSON", "Malformed event payload."),
                )
                continue

            # Event Dispatcher
            if event_name == "message.new":
                content = data.get("content")
                msg_type = data.get("type", "text")
                reply_to_str = data.get("reply_to_id")
                reply_to_id = uuid.UUID(reply_to_str) if reply_to_str else None

                async with db_session_module.async_session_factory() as session:
                    part = await ParticipantRepository().get_by_id(session, participant_id)
                    if not part:
                        continue
                    try:
                        msg_item = await message_service.send_message(
                            session=session,
                            room_id=room_id,
                            sender=part,
                            type=msg_type,
                            content=content,
                            reply_to_id=reply_to_id,
                        )
                        await session.commit()
                    except Exception as ex:
                        await ws_manager.send_personal(
                            room_id,
                            participant_id,
                            evt_error(room_id, "MESSAGE_FAILED", str(ex)),
                        )
                        continue

                # Broadcast persisted message to room
                envelope = evt_message_new(room_id, msg_item.model_dump(mode="json"))
                await ws_manager.broadcast(room_id, envelope)

            elif event_name == "message.delivered":
                msg_id_str = data.get("message_id")
                if msg_id_str:
                    msg_uuid = uuid.UUID(msg_id_str)
                    async with db_session_module.async_session_factory() as session:
                        receipt = await receipt_repo.mark_delivered(
                            session, msg_uuid, participant_id
                        )
                        await session.commit()
                        delivered_iso = (
                            receipt.delivered_at.isoformat() if receipt.delivered_at else ""
                        )

                    await ws_manager.broadcast(
                        room_id,
                        evt_message_delivered(room_id, msg_uuid, participant_id, delivered_iso),
                    )

            elif event_name == "message.read":
                msg_id_str = data.get("message_id")
                if msg_id_str:
                    msg_uuid = uuid.UUID(msg_id_str)
                    async with db_session_module.async_session_factory() as session:
                        receipt = await receipt_repo.mark_read(session, msg_uuid, participant_id)
                        await session.commit()
                        read_iso = receipt.read_at.isoformat() if receipt.read_at else ""

                    await ws_manager.broadcast(
                        room_id,
                        evt_message_read(room_id, msg_uuid, participant_id, read_iso),
                    )

            elif event_name == "typing.start":
                ws_manager.start_typing_timer(room_id, participant_id)
                await ws_manager.broadcast(
                    room_id,
                    evt_typing_start(room_id, participant_id, participant_nickname),
                    exclude_participant_id=participant_id,
                )

            elif event_name == "typing.stop":
                ws_manager.cancel_typing_timer(room_id, participant_id)
                await ws_manager.broadcast(
                    room_id,
                    evt_typing_stop(room_id, participant_id),
                    exclude_participant_id=participant_id,
                )

    except WebSocketDisconnect:
        is_last = await ws_manager.disconnect(room_id, participant_id, websocket)
        if is_last:
            async with db_session_module.async_session_factory() as session:
                count = await RoomRepository().get_participant_count(session, room_id)
            await ws_manager.broadcast(
                room_id,
                evt_room_member_left(room_id, participant_id, count, reason="disconnected"),
            )
    except Exception:
        await ws_manager.disconnect(room_id, participant_id, websocket)
