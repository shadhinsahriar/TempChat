"""Integration tests for message creation, replies, edits, deletes, and receipts."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_message_send_reply_edit_delete(client: AsyncClient):
    # 1. Create room
    create_res = await client.post(
        "/api/v1/rooms",
        json={"nickname": "Alice", "room_type": "group"},
    )
    room_id = create_res.json()["data"]["room"]["id"]
    alice_token = create_res.json()["data"]["guest_token"]
    code = create_res.json()["data"]["room"]["code"]
    headers_alice = {"Authorization": f"Bearer {alice_token}"}

    # 2. Bob joins
    join_res = await client.post(
        "/api/v1/rooms/join",
        json={"code": code, "nickname": "Bob"},
    )
    bob_token = join_res.json()["data"]["guest_token"]
    headers_bob = {"Authorization": f"Bearer {bob_token}"}

    # 3. Alice sends a text message
    msg1_res = await client.post(
        f"/api/v1/rooms/{room_id}/messages",
        json={"type": "text", "content": "Hello Bob!"},
        headers=headers_alice,
    )
    assert msg1_res.status_code == 201
    msg1_id = msg1_res.json()["data"]["id"]
    assert msg1_res.json()["data"]["content"] == "Hello Bob!"

    # 4. Bob replies to Alice's message
    reply_res = await client.post(
        f"/api/v1/rooms/{room_id}/messages",
        json={"type": "text", "content": "Hello Alice, nice to meet you!", "reply_to_id": msg1_id},
        headers=headers_bob,
    )
    assert reply_res.status_code == 201
    assert reply_res.json()["data"]["reply_to_id"] == msg1_id

    # 5. Invalid Reply Target (random UUID)
    bad_reply = await client.post(
        f"/api/v1/rooms/{room_id}/messages",
        json={"type": "text", "content": "Bad reply", "reply_to_id": str(uuid.uuid4())},
        headers=headers_bob,
    )
    assert bad_reply.status_code == 400
    assert bad_reply.json()["error"]["code"] == "INVALID_REPLY_TARGET"

    # 6. Bob edits his own message
    reply_id = reply_res.json()["data"]["id"]
    edit_res = await client.patch(
        f"/api/v1/rooms/{room_id}/messages/{reply_id}",
        json={"content": "Hello Alice, edited text!"},
        headers=headers_bob,
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["data"]["content"] == "Hello Alice, edited text!"
    assert edit_res.json()["data"]["edited_at"] is not None

    # 7. Alice attempts to edit Bob's message -> 403
    unauth_edit = await client.patch(
        f"/api/v1/rooms/{room_id}/messages/{reply_id}",
        json={"content": "Alice tampering with Bob's msg"},
        headers=headers_alice,
    )
    assert unauth_edit.status_code == 403
    assert unauth_edit.json()["error"]["code"] == "MESSAGE_NOT_EDITABLE"

    # 8. Bob marks Alice's message as read
    read_res = await client.post(
        f"/api/v1/rooms/{room_id}/messages/{msg1_id}/read",
        headers=headers_bob,
    )
    assert read_res.status_code == 200
    assert read_res.json()["data"]["read_at"] is not None

    # 9. List messages (paginated)
    list_res = await client.get(
        f"/api/v1/rooms/{room_id}/messages?limit=10&offset=0",
        headers=headers_alice,
    )
    assert list_res.status_code == 200
    assert list_res.json()["data"]["total"] == 2
    assert len(list_res.json()["data"]["messages"]) == 2

    # 10. Bob deletes his message
    del_res = await client.delete(
        f"/api/v1/rooms/{room_id}/messages/{reply_id}",
        headers=headers_bob,
    )
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted_at"] is not None
    assert del_res.json()["data"]["content"] is None
