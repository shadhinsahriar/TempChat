"""Pydantic schemas for WebSocket envelopes, tickets, and real-time events."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WSTicketResponse(BaseModel):
    ticket: str
    expires_in_seconds: int


class WSEventEnvelope(BaseModel):
    event: str = Field(..., description="Event type name, e.g. message.new")
    room_id: uuid.UUID = Field(..., description="Target room UUID")
    event_id: str = Field(..., description="Unique event ID for frontend deduplication")
    timestamp: datetime = Field(..., description="UTC ISO-8601 timestamp")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")


class ClientIncomingEvent(BaseModel):
    event: str
    data: dict[str, Any] = Field(default_factory=dict)
