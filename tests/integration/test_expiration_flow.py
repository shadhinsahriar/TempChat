"""Integration tests for room expiration, durable cleanup, and host early closure."""

import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import Room


@pytest.mark.asyncio
async def test_host_early_closure_purges_everything(client: AsyncClient, db_session: AsyncSession):
    # 1. Create Room
    create_res = await client.post(
        "/api/v1/rooms",
        json={"nickname": "HostAlice", "room_type": "group"},
    )
    room_id = create_res.json()["data"]["room"]["id"]
    token = create_res.json()["data"]["guest_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload file into room
    files = {
        "file": (
            "test.png",
            io.BytesIO(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            ),
            "image/png",
        ),
    }
    att_res = await client.post(
        f"/api/v1/rooms/{room_id}/attachments",
        files=files,
        headers=headers,
    )
    assert att_res.status_code == 201

    # 3. Host calls DELETE /api/v1/rooms/{room_id}
    del_res = await client.delete(f"/api/v1/rooms/{room_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 4. Room is now completely gone from database
    room_uuid = uuid.UUID(room_id)
    check = await db_session.execute(select(Room).where(Room.id == room_uuid))
    assert check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_expired_room_rejection(client: AsyncClient, db_session: AsyncSession):
    # 1. Create room
    create_res = await client.post(
        "/api/v1/rooms",
        json={"nickname": "Alice", "room_type": "group"},
    )
    room_id = create_res.json()["data"]["room"]["id"]
    token = create_res.json()["data"]["guest_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Directly expire the room in DB
    room_uuid = uuid.UUID(room_id)
    room = await db_session.get(Room, room_uuid)
    room.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    # 3. Accessing room info returns 410 ROOM_EXPIRED
    res = await client.get(f"/api/v1/rooms/{room_id}", headers=headers)
    assert res.status_code == 410
    assert res.json()["error"]["code"] == "ROOM_EXPIRED"
