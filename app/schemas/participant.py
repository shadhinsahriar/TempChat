"""Pydantic schemas for participants."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ParticipantItem(BaseModel):
    id: uuid.UUID
    nickname: str
    is_host: bool
    joined_at: datetime
    last_seen_at: datetime
    is_online: bool = False


class MemberListData(BaseModel):
    members: list[ParticipantItem]
    total_count: int
