"""Message SQLAlchemy model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, TZDateTime

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.participant import Participant
    from app.models.receipt import MessageReceipt
    from app.models.room import Room


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

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
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="text",  # 'text', 'image', 'file', 'audio'
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        TZDateTime,
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TZDateTime,
        nullable=True,
    )

    # Relationships
    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="messages",
        foreign_keys=[room_id],
    )
    sender: Mapped["Participant"] = relationship(
        "Participant",
        back_populates="messages",
        foreign_keys=[sender_id],
        lazy="selectin",
    )
    reply_to: Mapped[Optional["Message"]] = relationship(
        "Message",
        remote_side=[id],
        back_populates="replies",
        lazy="selectin",
    )
    replies: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="reply_to",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    receipts: Mapped[list["MessageReceipt"]] = relationship(
        "MessageReceipt",
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    __table_args__ = (Index("ix_messages_room_created", "room_id", "created_at"),)
