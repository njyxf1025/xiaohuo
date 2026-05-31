from __future__ import annotations

import io

import pytest


@pytest.mark.asyncio
async def test_upload_music(client, sample_wav_bytes):
    response = await client.post(
        "/api/music/upload",
        files={"file": ("test.wav", io.BytesIO(sample_wav_bytes), "audio/wav")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert data["filename"] == "test.wav"
    assert data["duration"] > 0
    assert data["sample_rate"] > 0
    assert data["channels"] >= 1
    assert "format" in data


@pytest.mark.asyncio
async def test_upload_music_invalid_format(client):
    response = await client.post(
        "/api/music/upload",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_music_no_filename(client, sample_wav_bytes):
    response = await client.post(
        "/api/music/upload",
        files={"file": ("", io.BytesIO(sample_wav_bytes), "audio/wav")},
    )
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_trim_music(client, sample_wav_bytes):
    upload_resp = await client.post(
        "/api/music/upload",
        files={"file": ("test.wav", io.BytesIO(sample_wav_bytes), "audio/wav")},
    )
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["file_id"]

    trim_resp = await client.post(
        "/api/music/trim",
        json={"file_id": file_id, "start_time": 0.0, "end_time": 1.0},
    )
    assert trim_resp.status_code == 200
    data = trim_resp.json()
    assert data["file_id"] == file_id
    assert data["start_time"] == 0.0
    assert data["end_time"] == 1.0


@pytest.mark.asyncio
async def test_trim_music_invalid_time_range(client, sample_wav_bytes):
    upload_resp = await client.post(
        "/api/music/upload",
        files={"file": ("test.wav", io.BytesIO(sample_wav_bytes), "audio/wav")},
    )
    file_id = upload_resp.json()["file_id"]

    trim_resp = await client.post(
        "/api/music/trim",
        json={"file_id": file_id, "start_time": 2.0, "end_time": 1.0},
    )
    assert trim_resp.status_code == 400


@pytest.mark.asyncio
async def test_trim_music_not_found(client):
    trim_resp = await client.post(
        "/api/music/trim",
        json={"file_id": "nonexistent-id", "start_time": 0.0, "end_time": 1.0},
    )
    assert trim_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_waveform(client, sample_wav_bytes):
    upload_resp = await client.post(
        "/api/music/upload",
        files={"file": ("test.wav", io.BytesIO(sample_wav_bytes), "audio/wav")},
    )
    file_id = upload_resp.json()["file_id"]

    waveform_resp = await client.get(f"/api/music/waveform/{file_id}")
    assert waveform_resp.status_code == 200
    data = waveform_resp.json()
    assert data["file_id"] == file_id
    assert isinstance(data["waveform"], list)
    assert len(data["waveform"]) > 0
    assert data["sample_rate"] > 0
    assert data["duration"] > 0


@pytest.mark.asyncio
async def test_get_waveform_not_found(client):
    response = await client.get("/api/music/waveform/nonexistent-id")
    assert response.status_code == 404
