"""Tests for database models, relationships, and cascades."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_guest_token, hash_guest_token, hash_password
from app.models import (
    Attachment,
    DeletionTask,
    Message,
    MessageReceipt,
    Participant,
    Room,
)


@pytest.mark.asyncio
async def test_room_and_participant_creation(db_session: AsyncSession):
    now = datetime.now(UTC)
    room = Room(
        code="ABC999",
        room_type="group",
        password_hash=hash_password("testpass"),
        max_members=10,
        expires_at=now + timedelta(hours=1),
        status="active",
    )
    db_session.add(room)
    await db_session.flush()

    raw_token = generate_guest_token()
    participant = Participant(
        room_id=room.id,
        nickname="Alice",
        token_hash=hash_guest_token(raw_token),
        is_host=True,
    )
    db_session.add(participant)
    await db_session.flush()

    room.host_participant_id = participant.id
    await db_session.commit()

    # Query back
    result = await db_session.execute(select(Room).where(Room.id == room.id))
    fetched_room = result.scalar_one()

    assert fetched_room.code == "ABC999"
    assert fetched_room.host_participant_id == participant.id
    assert len(fetched_room.participants) == 1
    assert fetched_room.participants[0].nickname == "Alice"


@pytest.mark.asyncio
async def test_message_reply_and_cascade_delete(db_session: AsyncSession):
    now = datetime.now(UTC)
    room = Room(
        code="GRP123",
        room_type="group",
        max_members=20,
        expires_at=now + timedelta(hours=2),
    )
    db_session.add(room)
    await db_session.flush()

    p1 = Participant(
        room_id=room.id,
        nickname="Bob",
        token_hash=hash_guest_token(generate_guest_token()),
        is_host=True,
    )
    p2 = Participant(
        room_id=room.id,
        nickname="Charlie",
        token_hash=hash_guest_token(generate_guest_token()),
        is_host=False,
    )
    db_session.add_all([p1, p2])
    await db_session.flush()

    msg1 = Message(
        room_id=room.id,
        sender_id=p1.id,
        type="text",
        content="First message",
    )
    db_session.add(msg1)
    await db_session.flush()

    msg2 = Message(
        room_id=room.id,
        sender_id=p2.id,
        type="text",
        content="Reply to first message",
        reply_to_id=msg1.id,
    )
    attachment = Attachment(
        message_id=msg1.id,
        room_id=room.id,
        storage_key=f"uploads/{uuid.uuid4()}.png",
        original_filename="screenshot.png",
        mime_type="image/png",
        size_bytes=1024,
        media_type="image",
    )
    receipt = MessageReceipt(
        message_id=msg1.id,
        participant_id=p2.id,
        delivered_at=now,
    )
    db_session.add_all([msg2, attachment, receipt])
    await db_session.commit()

    # Verify relationships
    res = await db_session.execute(select(Message).where(Message.id == msg2.id))
    fetched_msg2 = res.scalar_one()
    assert fetched_msg2.reply_to_id == msg1.id

    # Test Cascade Delete of Room
    await db_session.delete(room)
    await db_session.commit()

    # Participants, messages, attachments, receipts must be gone
    p_check = await db_session.execute(select(Participant).where(Participant.room_id == room.id))
    assert p_check.scalars().all() == []

    m_check = await db_session.execute(select(Message).where(Message.room_id == room.id))
    assert m_check.scalars().all() == []

    a_check = await db_session.execute(select(Attachment).where(Attachment.room_id == room.id))
    assert a_check.scalars().all() == []

    r_check = await db_session.execute(
        select(MessageReceipt).where(MessageReceipt.message_id == msg1.id)
    )
    assert r_check.scalars().all() == []


@pytest.mark.asyncio
async def test_deletion_task_outbox(db_session: AsyncSession):
    room_id = uuid.uuid4()
    task = DeletionTask(
        room_id=room_id,
        storage_keys=["key1.png", "key2.pdf"],
        status="pending",
    )
    db_session.add(task)
    await db_session.commit()

    res = await db_session.execute(select(DeletionTask).where(DeletionTask.room_id == room_id))
    fetched_task = res.scalar_one()
    assert fetched_task.status == "pending"
    assert fetched_task.storage_keys == ["key1.png", "key2.pdf"]
    assert fetched_task.retry_count == 0
