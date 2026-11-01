"""Integration tests for room endpoints, authentication, and access control."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_room(client: AsyncClient):
    # 1. Create a group room
    payload = {
        "nickname": "HostAlice",
        "room_type": "group",
        "duration_minutes": 60,
        "max_members": 10,
        "password": "strongPassword123",
    }
    res = await client.post("/api/v1/rooms", json=payload)
    assert res.status_code == 201
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["data"]["room"]["code"] is not None
    assert res_data["data"]["room"]["room_type"] == "group"
    assert res_data["data"]["participant"]["nickname"] == "HostAlice"
    assert res_data["data"]["participant"]["is_host"] is True

    room_id = res_data["data"]["room"]["id"]
    guest_token = res_data["data"]["guest_token"]
    invite_code = res_data["data"]["room"]["code"]

    # 2. Query room details with Bearer token
    headers = {"Authorization": f"Bearer {guest_token}"}
    detail_res = await client.get(f"/api/v1/rooms/{room_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["data"]["code"] == invite_code
    assert detail_res.json()["data"]["is_password_protected"] is True
    assert detail_res.json()["data"]["member_count"] == 1


@pytest.mark.asyncio
async def test_room_join_with_password(client: AsyncClient):
    # Create password-protected room
    create_res = await client.post(
        "/api/v1/rooms",
        json={
            "nickname": "HostUser",
            "room_type": "group",
            "duration_minutes": 30,
            "password": "SecretPassword1",
        },
    )
    code = create_res.json()["data"]["room"]["code"]

    # Attempt join with missing password -> 401
    bad_res1 = await client.post(
        "/api/v1/rooms/join",
        json={"code": code, "nickname": "Guest1"},
    )
    assert bad_res1.status_code == 401
    assert bad_res1.json()["error"]["code"] == "PASSWORD_REQUIRED"

    # Attempt join with wrong password -> 401
    bad_res2 = await client.post(
        "/api/v1/rooms/join",
        json={"code": code, "nickname": "Guest1", "password": "WrongPassword"},
    )
    assert bad_res2.status_code == 401
    assert bad_res2.json()["error"]["code"] == "INVALID_PASSWORD"

    # Successful join with correct password
    join_res = await client.post(
        "/api/v1/rooms/join",
        json={"code": code, "nickname": "Guest1", "password": "SecretPassword1"},
    )
    assert join_res.status_code == 200
    assert join_res.json()["success"] is True
    assert join_res.json()["data"]["participant"]["nickname"] == "Guest1"
    assert join_res.json()["data"]["participant"]["is_host"] is False


@pytest.mark.asyncio
async def test_private_room_two_member_limit(client: AsyncClient):
    # Create private room (limit = 2)
    create_res = await client.post(
        "/api/v1/rooms",
        json={"nickname": "User1", "room_type": "private", "duration_minutes": 10},
    )
    code = create_res.json()["data"]["room"]["code"]

    # Second user joins (success)
    join_res = await client.post(
        "/api/v1/rooms/join",
        json={"code": code, "nickname": "User2"},
    )
    assert join_res.status_code == 200

    # Third user tries to join -> 403 ROOM_FULL
    full_res = await client.post(
        "/api/v1/rooms/join",
        json={"code": code, "nickname": "User3"},
    )
    assert full_res.status_code == 403
    assert full_res.json()["error"]["code"] == "ROOM_FULL"


@pytest.mark.asyncio
async def test_cross_room_access_denial(client: AsyncClient):
    # Create Room 1
    r1 = await client.post(
        "/api/v1/rooms",
        json={"nickname": "UserR1", "room_type": "group"},
    )
    token_r1 = r1.json()["data"]["guest_token"]

    # Create Room 2
    r2 = await client.post(
        "/api/v1/rooms",
        json={"nickname": "UserR2", "room_type": "group"},
    )
    room2_id = r2.json()["data"]["room"]["id"]

    # Try to access Room 2 using Room 1's token -> 403 FORBIDDEN_ROOM_ACCESS
    headers = {"Authorization": f"Bearer {token_r1}"}
    access_res = await client.get(f"/api/v1/rooms/{room2_id}", headers=headers)
    assert access_res.status_code == 403
    assert access_res.json()["error"]["code"] == "FORBIDDEN_ROOM_ACCESS"
