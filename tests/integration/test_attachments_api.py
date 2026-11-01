"""Integration tests for media attachment uploads and secure streaming."""

import io

import pytest
from httpx import AsyncClient

# Valid minimal PNG header bytes
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"


@pytest.mark.asyncio
async def test_upload_and_retrieve_attachment(client: AsyncClient):
    # 1. Create Room
    create_res = await client.post(
        "/api/v1/rooms",
        json={"nickname": "Uploader", "room_type": "group"},
    )
    room_id = create_res.json()["data"]["room"]["id"]
    token = create_res.json()["data"]["guest_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload valid PNG image
    files = {
        "file": ("image.png", io.BytesIO(VALID_PNG_BYTES), "image/png"),
    }
    upload_res = await client.post(
        f"/api/v1/rooms/{room_id}/attachments",
        files=files,
        headers=headers,
    )
    assert upload_res.status_code == 201
    att_data = upload_res.json()["data"]
    att_id = att_data["id"]
    assert att_data["media_type"] == "image"
    assert att_data["mime_type"] == "image/png"
    assert att_data["original_filename"] == "image.png"

    # 3. Retrieve attachment stream
    get_res = await client.get(
        f"/api/v1/rooms/{room_id}/attachments/{att_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    assert get_res.headers["content-type"] == "image/png"
    assert get_res.content == VALID_PNG_BYTES


@pytest.mark.asyncio
async def test_reject_dangerous_attachment(client: AsyncClient):
    # 1. Create Room
    create_res = await client.post(
        "/api/v1/rooms",
        json={"nickname": "Uploader2", "room_type": "group"},
    )
    room_id = create_res.json()["data"]["room"]["id"]
    token = create_res.json()["data"]["guest_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Attempt uploading dangerous script (.sh)
    files = {
        "file": ("malicious.sh", io.BytesIO(b"#!/bin/bash\necho bad"), "text/x-shellscript"),
    }
    bad_res = await client.post(
        f"/api/v1/rooms/{room_id}/attachments",
        files=files,
        headers=headers,
    )
    assert bad_res.status_code == 400
    assert bad_res.json()["error"]["code"] == "INVALID_ATTACHMENT"
