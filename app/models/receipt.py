"""Message Receipt SQLAlchemy model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TZDateTime

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.participant import Participant


class MessageReceipt(Base):
    __tablename__ = "message_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        TZDateTime,
        nullable=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        TZDateTime,
        nullable=True,
    )

    # Relationships
    message: Mapped["Message"] = relationship(
        "Message",
        back_populates="receipts",
        foreign_keys=[message_id],
    )
    participant: Mapped["Participant"] = relationship(
        "Participant",
        back_populates="receipts",
        foreign_keys=[participant_id],
    )

    __table_args__ = (
        UniqueConstraint("message_id", "participant_id", name="uq_message_receipt_participant"),
        Index("ix_receipts_participant_read", "participant_id", "read_at"),
    )
