"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-01 09:18:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rooms
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("room_type", sa.String(length=16), nullable=False, server_default="group"),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("host_participant_id", sa.Uuid(), nullable=True),
        sa.Column("max_members", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rooms")),
        sa.UniqueConstraint("code", name=op.f("uq_rooms_code")),
    )
    op.create_index(
        "ix_rooms_code", "rooms", ["code"], unique=True
    )
    op.create_index(
        "ix_rooms_status_expires_at", "rooms", ["status", "expires_at"], unique=False
    )

    # 2. Participants
    op.create_table(
        "participants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("nickname", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("is_host", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name=op.f("fk_participants_room_id_rooms"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_participants")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_participants_token_hash")),
    )
    op.create_index(
        "ix_participants_room_id", "participants", ["room_id"], unique=False
    )
    op.create_index(
        "ix_participants_token_hash", "participants", ["token_hash"], unique=True
    )
    op.create_index(
        "ix_participants_room_host", "participants", ["room_id", "is_host"], unique=False
    )
    op.create_index(
        "ix_participants_room_last_seen", "participants", ["room_id", "last_seen_at"], unique=False
    )

    # 3. Messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("reply_to_id", sa.Uuid(), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name=op.f("fk_messages_room_id_rooms"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"], ["participants.id"], name=op.f("fk_messages_sender_id_participants"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_id"], ["messages.id"], name=op.f("fk_messages_reply_to_id_messages"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "ix_messages_room_id", "messages", ["room_id"], unique=False
    )
    op.create_index(
        "ix_messages_sender_id", "messages", ["sender_id"], unique=False
    )
    op.create_index(
        "ix_messages_reply_to_id", "messages", ["reply_to_id"], unique=False
    )
    op.create_index(
        "ix_messages_room_created", "messages", ["room_id", "created_at"], unique=False
    )

    # 4. Attachments
    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], name=op.f("fk_attachments_message_id_messages"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name=op.f("fk_attachments_room_id_rooms"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachments")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_attachments_storage_key")),
    )
    op.create_index(
        "ix_attachments_message_id", "attachments", ["message_id"], unique=False
    )
    op.create_index(
        "ix_attachments_room_id", "attachments", ["room_id"], unique=False
    )
    op.create_index(
        "ix_attachments_storage_key", "attachments", ["storage_key"], unique=True
    )
    op.create_index(
        "ix_attachments_room_media", "attachments", ["room_id", "media_type"], unique=False
    )

    # 5. Message Receipts
    op.create_table(
        "message_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], name=op.f("fk_message_receipts_message_id_messages"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"], ["participants.id"], name=op.f("fk_message_receipts_participant_id_participants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_receipts")),
        sa.UniqueConstraint("message_id", "participant_id", name="uq_message_receipt_participant"),
    )
    op.create_index(
        "ix_message_receipts_message_id", "message_receipts", ["message_id"], unique=False
    )
    op.create_index(
        "ix_message_receipts_participant_id", "message_receipts", ["participant_id"], unique=False
    )
    op.create_index(
        "ix_receipts_participant_read", "message_receipts", ["participant_id", "read_at"], unique=False
    )

    # 6. Deletion Tasks (Outbox)
    op.create_table(
        "deletion_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("storage_keys", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deletion_tasks")),
    )
    op.create_index(
        "ix_deletion_tasks_room_id", "deletion_tasks", ["room_id"], unique=False
    )
    op.create_index(
        "ix_deletion_tasks_status_retries", "deletion_tasks", ["status", "retry_count"], unique=False
    )


def downgrade() -> None:
    op.drop_table("deletion_tasks")
    op.drop_table("message_receipts")
    op.drop_table("attachments")
    op.drop_table("messages")
    op.drop_table("participants")
    op.drop_table("rooms")
