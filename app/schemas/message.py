"""Pydantic schemas for messages and receipts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class MessageCreateRequest(BaseModel):
    type: str = Field(default="text", description="'text', 'image', 'file', or 'audio'")
    content: str | None = Field(default=None, max_length=10000, description="Message text")
    reply_to_id: uuid.UUID | None = Field(default=None, description="Optional parent message ID")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        val = v.lower().strip()
        if val not in {"text", "image", "file", "audio"}:
            raise ValueError("type must be 'text', 'image', 'file', or 'audio'")
        return val


class MessageUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000, description="Updated message content")


class AttachmentBrief(BaseModel):
    id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    media_type: str


class ReceiptBrief(BaseModel):
    participant_id: uuid.UUID
    delivered_at: datetime | None = None
    read_at: datetime | None = None


class MessageItem(BaseModel):
    id: uuid.UUID
    room_id: uuid.UUID
    sender_id: uuid.UUID
    sender_nickname: str
    type: str
    content: str | None
    reply_to_id: uuid.UUID | None
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    attachments: list[AttachmentBrief] = []
    receipts: list[ReceiptBrief] = []


class MessageListData(BaseModel):
    messages: list[MessageItem]
    total: int
    limit: int
    offset: int
    has_more: bool
