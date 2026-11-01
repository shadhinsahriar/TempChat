"""Integration tests for WebSocket ticket exchange, events, and single-use validation."""

import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient

from app.main import app
from app.websocket.tickets import ticket_store


@pytest.mark.asyncio
async def test_websocket_ticket_issuance_and_single_use(client: AsyncClient):
    # 1. Create Room
    create_res = await client.post(
        "/api/v1/rooms",
        json={"nickname": "Alice", "room_type": "group"},
    )
    room_id = create_res.json()["data"]["room"]["id"]
    token = create_res.json()["data"]["guest_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Issue ticket
    ticket_res = await client.post(
        f"/api/v1/rooms/{room_id}/ws-ticket",
        headers=headers,
    )
    assert ticket_res.status_code == 200
    ticket = ticket_res.json()["data"]["ticket"]
    assert len(ticket) >= 32

    # 3. First consumption of ticket succeeds
    import uuid

    room_uuid = uuid.UUID(room_id)
    participant_id = await ticket_store.consume_ticket(ticket, room_uuid)
    assert participant_id is not None

    # 4. Second consumption of the same ticket fails (single-use guarantee)
    second_try = await ticket_store.consume_ticket(ticket, room_uuid)
    assert second_try is None


@pytest.mark.asyncio
async def test_websocket_connection_and_message_broadcast(client: AsyncClient):
    # 1. Create room
    create_res = await client.post(
        "/api/v1/rooms",
        json={"nickname": "Alice", "room_type": "group"},
    )
    room_id = create_res.json()["data"]["room"]["id"]
    token = create_res.json()["data"]["guest_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Issue ticket
    ticket_res = await client.post(
        f"/api/v1/rooms/{room_id}/ws-ticket",
        headers=headers,
    )
    ticket = ticket_res.json()["data"]["ticket"]

    # 3. Connect over WebSocket
    with TestClient(app) as test_client:
        with test_client.websocket_connect(f"/api/v1/ws/rooms/{room_id}?ticket={ticket}") as ws:
            # First message received is room.joined, then room.members
            joined_event = ws.receive_json()
            assert joined_event["event"] == "room.joined"

            roster_event = ws.receive_json()
            assert roster_event["event"] == "room.members"
            assert roster_event["data"]["total_count"] >= 1

            # Send typing event
            ws.send_json({"event": "typing.start", "data": {}})

            # Send chat message
            ws.send_json(
                {"event": "message.new", "data": {"type": "text", "content": "Hello real-time!"}}
            )
            new_msg_event = ws.receive_json()
            assert new_msg_event["event"] == "message.new"
            assert new_msg_event["data"]["content"] == "Hello real-time!"
