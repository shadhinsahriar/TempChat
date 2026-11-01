"""Pydantic schemas for rooms."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RoomCreateRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=32, description="Creator guest nickname")
    room_type: str = Field(default="group", description="'private' or 'group'")
    duration_minutes: int = Field(default=60, description="Room duration in minutes")
    max_members: int | None = Field(default=None, description="Max allowed members")
    password: str | None = Field(
        default=None, min_length=4, max_length=128, description="Optional room password"
    )

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Nickname cannot be empty or whitespace only")
        return stripped

    @field_validator("room_type")
    @classmethod
    def validate_room_type(cls, v: str) -> str:
        val = v.lower().strip()
        if val not in {"private", "group"}:
            raise ValueError("room_type must be either 'private' or 'group'")
        return val


class RoomJoinRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=16, description="Invitation code")
    nickname: str = Field(..., min_length=1, max_length=32, description="Guest nickname")
    password: str | None = Field(default=None, description="Room password if protected")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Nickname cannot be empty or whitespace only")
        return stripped


class RoomInfo(BaseModel):
    id: uuid.UUID
    code: str
    invite_url: str
    room_type: str
    expires_at: datetime
    max_members: int


class ParticipantBrief(BaseModel):
    id: uuid.UUID
    nickname: str
    is_host: bool


class RoomCreatedData(BaseModel):
    room: RoomInfo
    participant: ParticipantBrief
    guest_token: str


class RoomJoinedData(BaseModel):
    room: RoomInfo
    participant: ParticipantBrief
    guest_token: str


class RoomDetailData(BaseModel):
    id: uuid.UUID
    code: str
    invite_url: str
    room_type: str
    expires_at: datetime
    max_members: int
    member_count: int
    is_password_protected: bool
    status: str
