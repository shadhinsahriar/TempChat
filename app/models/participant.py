"""Participant SQLAlchemy model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TZDateTime, utc_now

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.receipt import MessageReceipt
    from app.models.room import Room


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nickname: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    is_host: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        default=utc_now,
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="participants",
        foreign_keys=[room_id],
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="sender",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    receipts: Mapped[list["MessageReceipt"]] = relationship(
        "MessageReceipt",
        back_populates="participant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_participants_room_host", "room_id", "is_host"),
        Index("ix_participants_room_last_seen", "room_id", "last_seen_at"),
    )
