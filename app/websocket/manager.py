"""In-memory WebSocket connection manager with multi-tab support and typing debouncer."""

import asyncio
import json
import uuid
from collections import defaultdict

from fastapi import WebSocket

from app.core.config import settings
from app.schemas.websocket import WSEventEnvelope
from app.websocket.events import evt_room_expired, evt_typing_stop


class ConnectionManager:
    def __init__(self):
        # room_id -> participant_id -> set of active WebSockets
        self._connections: dict[uuid.UUID, dict[uuid.UUID, set[WebSocket]]] = defaultdict(
            lambda: defaultdict(set)
        )
        self._typing_timers: dict[tuple[uuid.UUID, uuid.UUID], asyncio.TimerHandle] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        room_id: uuid.UUID,
        participant_id: uuid.UUID,
        websocket: WebSocket,
    ) -> bool:
        """Register WebSocket. Returns True if this is the participant's first connection."""
        async with self._lock:
            first_socket = len(self._connections[room_id][participant_id]) == 0
            self._connections[room_id][participant_id].add(websocket)
            return first_socket

    async def disconnect(
        self,
        room_id: uuid.UUID,
        participant_id: uuid.UUID,
        websocket: WebSocket,
    ) -> bool:
        """Unregister WebSocket. Returns True if the participant has no remaining sockets."""
        async with self._lock:
            participant_sockets = self._connections[room_id].get(participant_id, set())
            participant_sockets.discard(websocket)

            if not participant_sockets:
                self._connections[room_id].pop(participant_id, None)
                if not self._connections[room_id]:
                    self._connections.pop(room_id, None)
                return True
            return False

    def is_online(self, room_id: uuid.UUID, participant_id: uuid.UUID) -> bool:
        return bool(self._connections.get(room_id, {}).get(participant_id))

    def get_online_participants(self, room_id: uuid.UUID) -> set[uuid.UUID]:
        return set(self._connections.get(room_id, {}).keys())

    async def send_personal(
        self,
        room_id: uuid.UUID,
        participant_id: uuid.UUID,
        envelope: WSEventEnvelope,
    ) -> None:
        """Send event envelope to all sockets belonging to a specific participant."""
        sockets = list(self._connections.get(room_id, {}).get(participant_id, set()))
        message_json = json.dumps(envelope.model_dump(mode="json"))
        for ws in sockets:
            try:
                await ws.send_text(message_json)
            except Exception:
                pass

    async def broadcast(
        self,
        room_id: uuid.UUID,
        envelope: WSEventEnvelope,
        exclude_participant_id: uuid.UUID | None = None,
    ) -> None:
        """Broadcast event envelope to all connected sockets in a room."""
        room_map = self._connections.get(room_id, {})
        message_json = json.dumps(envelope.model_dump(mode="json"))

        send_coroutines = []
        for pid, sockets in room_map.items():
            if exclude_participant_id is not None and pid == exclude_participant_id:
                continue
            for ws in list(sockets):
                send_coroutines.append(self._safe_send(ws, message_json))

        if send_coroutines:
            await asyncio.gather(*send_coroutines, return_exceptions=True)

    async def _safe_send(self, ws: WebSocket, message_json: str) -> None:
        try:
            await ws.send_text(message_json)
        except Exception:
            pass

    def start_typing_timer(
        self,
        room_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> None:
        """Schedule automatic typing.stop event after timeout."""
        key = (room_id, participant_id)
        if key in self._typing_timers:
            self._typing_timers[key].cancel()

        loop = asyncio.get_running_loop()
        timer = loop.call_later(
            settings.WS_TYPING_TIMEOUT_SECONDS,
            lambda: asyncio.create_task(
                self.broadcast(room_id, evt_typing_stop(room_id, participant_id))
            ),
        )
        self._typing_timers[key] = timer

    def cancel_typing_timer(self, room_id: uuid.UUID, participant_id: uuid.UUID) -> None:
        key = (room_id, participant_id)
        timer = self._typing_timers.pop(key, None)
        if timer:
            timer.cancel()

    async def close_room_connections(
        self,
        room_id: uuid.UUID,
        reason: str = "Room has expired.",
    ) -> None:
        """Notify all sockets that the room expired and gracefully close them."""
        envelope = evt_room_expired(room_id, reason=reason)
        await self.broadcast(room_id, envelope)

        async with self._lock:
            room_map = self._connections.pop(room_id, {})
            for sockets in room_map.values():
                for ws in list(sockets):
                    try:
                        await ws.close(code=1000, reason=reason)
                    except Exception:
                        pass


ws_manager = ConnectionManager()
