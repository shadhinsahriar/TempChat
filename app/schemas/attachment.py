"""Pydantic schemas for attachments."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AttachmentData(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    room_id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    media_type: str
    created_at: datetime
