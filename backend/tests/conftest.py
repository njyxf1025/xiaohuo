from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def sample_wav(tmp_path) -> Path:
    sr = 22050
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
    wav_path = tmp_path / "test_audio.wav"
    sf.write(str(wav_path), audio, sr)
    return wav_path


@pytest.fixture
def sample_wav_bytes(sample_wav) -> bytes:
    return sample_wav.read_bytes()


@pytest.fixture
def sample_png(tmp_path) -> Path:
    from PIL import Image

    img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
    png_path = tmp_path / "test_image.png"
    img.save(str(png_path))
    return png_path


@pytest.fixture
def sample_png_bytes(sample_png) -> bytes:
    return sample_png.read_bytes()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
