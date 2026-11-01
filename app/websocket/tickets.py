"""Single-use, short-lived WebSocket ticket store."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from app.core.config import settings
from app.core.security import generate_ticket


class TicketRecord(NamedTuple):
    room_id: uuid.UUID
    participant_id: uuid.UUID
    expires_at: datetime


class TicketStore:
    def __init__(self):
        self._tickets: dict[str, TicketRecord] = {}
        self._lock = asyncio.Lock()

    async def create_ticket(
        self,
        room_id: uuid.UUID,
        participant_id: uuid.UUID,
        ttl_seconds: int = settings.WS_TICKET_TTL_SECONDS,
    ) -> str:
        ticket = generate_ticket()
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

        async with self._lock:
            # Clean expired tickets opportunistically
            now = datetime.now(UTC)
            expired_keys = [k for k, v in self._tickets.items() if v.expires_at <= now]
            for k in expired_keys:
                del self._tickets[k]

            self._tickets[ticket] = TicketRecord(
                room_id=room_id,
                participant_id=participant_id,
                expires_at=expires_at,
            )

        return ticket

    async def consume_ticket(
        self,
        ticket: str,
        expected_room_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """Atomically pop and validate a single-use ticket. Return participant_id if valid."""
        async with self._lock:
            record = self._tickets.pop(ticket, None)
            if not record:
                return None

            now = datetime.now(UTC)
            if record.expires_at <= now:
                return None

            if record.room_id != expected_room_id:
                return None

            return record.participant_id


ticket_store = TicketStore()
