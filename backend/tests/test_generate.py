from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_generation_task_invalid_model(client, sample_wav_bytes, sample_png_bytes):
    with patch("app.services.avatar_service.detect_face") as mock_detect:
        mock_detect.return_value = {
            "face_detected": True,
            "face_count": 1,
            "face_locations": [[10, 80, 80, 10]],
            "warning": None,
            "error": None,
        }
        upload_music_resp = await client.post(
            "/api/music/upload",
            files={"file": ("test.wav", io.BytesIO(sample_wav_bytes), "audio/wav")},
        )
        upload_avatar_resp = await client.post(
            "/api/avatar/upload",
            files={"file": ("face.png", io.BytesIO(sample_png_bytes), "image/png")},
        )

    music_file_id = upload_music_resp.json()["file_id"]
    avatar_id = upload_avatar_resp.json()["avatar_id"]

    gen_resp = await client.post(
        "/api/generate",
        json={
            "music_file_id": music_file_id,
            "avatar_id": avatar_id,
            "model": "invalid_model",
        },
    )
    assert gen_resp.status_code == 400


@pytest.mark.asyncio
async def test_create_generation_task_music_not_found(client, sample_png_bytes):
    with patch("app.services.avatar_service.detect_face") as mock_detect:
        mock_detect.return_value = {
            "face_detected": True,
            "face_count": 1,
            "face_locations": [[10, 80, 80, 10]],
            "warning": None,
            "error": None,
        }
        upload_avatar_resp = await client.post(
            "/api/avatar/upload",
            files={"file": ("face.png", io.BytesIO(sample_png_bytes), "image/png")},
        )

    avatar_id = upload_avatar_resp.json()["avatar_id"]

    gen_resp = await client.post(
        "/api/generate",
        json={
            "music_file_id": "nonexistent-music",
            "avatar_id": avatar_id,
            "model": "wav2lip",
        },
    )
    assert gen_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_generation_task_avatar_not_found(client, sample_wav_bytes):
    upload_music_resp = await client.post(
        "/api/music/upload",
        files={"file": ("test.wav", io.BytesIO(sample_wav_bytes), "audio/wav")},
    )
    music_file_id = upload_music_resp.json()["file_id"]

    gen_resp = await client.post(
        "/api/generate",
        json={
            "music_file_id": music_file_id,
            "avatar_id": "nonexistent-avatar",
            "model": "wav2lip",
        },
    )
    assert gen_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_task_status_not_found(client):
    response = await client.get("/api/generate/nonexistent-task/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_result_not_found(client):
    response = await client.get("/api/generate/nonexistent-task/result")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_generation_history(client):
    response = await client.get("/api/generate/history")
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert "total" in data
    assert isinstance(data["tasks"], list)


@pytest.mark.asyncio
async def test_create_generation_task_success(client, sample_wav_bytes, sample_png_bytes):
    with patch("app.services.avatar_service.detect_face") as mock_detect:
        mock_detect.return_value = {
            "face_detected": True,
            "face_count": 1,
            "face_locations": [[10, 80, 80, 10]],
            "warning": None,
            "error": None,
        }
        upload_music_resp = await client.post(
            "/api/music/upload",
            files={"file": ("test.wav", io.BytesIO(sample_wav_bytes), "audio/wav")},
        )
        upload_avatar_resp = await client.post(
            "/api/avatar/upload",
            files={"file": ("face.png", io.BytesIO(sample_png_bytes), "image/png")},
        )

    music_file_id = upload_music_resp.json()["file_id"]
    avatar_id = upload_avatar_resp.json()["avatar_id"]

    with patch.object(
        __import__("app.services.generation_service", fromlist=["task_manager"]).task_manager,
        "run_task",
        new_callable=AsyncMock,
    ) as mock_run:
        gen_resp = await client.post(
            "/api/generate",
            json={
                "music_file_id": music_file_id,
                "avatar_id": avatar_id,
                "model": "wav2lip",
            },
        )
        assert gen_resp.status_code == 200
        data = gen_resp.json()
        assert "task_id" in data

        status_resp = await client.get(f"/api/generate/{data['task_id']}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["task_id"] == data["task_id"]
        assert status_data["status"] in ("pending", "processing", "completed", "failed")
