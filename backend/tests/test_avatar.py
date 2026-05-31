from __future__ import annotations

import io
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_upload_avatar_image(client, sample_png_bytes):
    with patch("app.services.avatar_service.detect_face") as mock_detect:
        mock_detect.return_value = {
            "face_detected": True,
            "face_count": 1,
            "face_locations": [[10, 80, 80, 10]],
            "warning": None,
            "error": None,
        }
        response = await client.post(
            "/api/avatar/upload",
            files={"file": ("face.png", io.BytesIO(sample_png_bytes), "image/png")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "avatar_id" in data
    assert data["file_type"] == "image/png"
    assert "preview_url" in data
    assert data["face_detection"]["face_detected"] is True


@pytest.mark.asyncio
async def test_upload_avatar_invalid_type(client):
    response = await client.post(
        "/api/avatar/upload",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_avatars(client):
    response = await client.get("/api/avatar/list")
    assert response.status_code == 200
    data = response.json()
    assert "avatars" in data
    assert "total" in data
    assert isinstance(data["avatars"], list)


@pytest.mark.asyncio
async def test_get_avatar_not_found(client):
    response = await client.get("/api/avatar/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_avatar_not_found(client):
    response = await client.delete("/api/avatar/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_preset_avatar(client):
    response = await client.delete("/api/avatar/preset-001")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_avatar_preview_not_found(client):
    response = await client.get("/api/avatar/nonexistent-id/preview")
    assert response.status_code == 404
