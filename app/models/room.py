"""Room SQLAlchemy model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, TZDateTime

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.message import Message
    from app.models.participant import Participant


class Room(Base, TimestampMixin):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        index=True,
        nullable=False,
    )
    room_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="group",  # 'private' or 'group'
    )
    password_hash: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    host_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    max_members: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )
    expires_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",  # 'active', 'deleting', 'expired'
    )

    # Relationships
    participants: Mapped[list["Participant"]] = relationship(
        "Participant",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Participant.room_id",
        lazy="selectin",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Message.room_id",
        lazy="selectin",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Attachment.room_id",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_rooms_status_expires_at", "status", "expires_at"),)
