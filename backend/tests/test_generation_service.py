from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.generation_service import ModelScheduler


def test_model_scheduler_lazy_init():
    scheduler = ModelScheduler()
    assert len(scheduler._engines) == 0
    assert len(scheduler._loaded) == 0


def test_model_scheduler_lazy_load():
    scheduler = ModelScheduler()
    mock_engine = MagicMock()
    mock_engine.process.return_value = {"success": True, "output_path": "/tmp/out.mp4", "duration": 1.0, "error": None}

    with patch("app.services.generation_service._import_class") as mock_import:
        mock_import.return_value = MagicMock(return_value=mock_engine)
        engine = scheduler.get_engine("wav2lip")
        assert engine is mock_engine
        assert scheduler.is_engine_loaded("wav2lip")


def test_model_scheduler_cache():
    scheduler = ModelScheduler()
    mock_engine = MagicMock()

    with patch("app.services.generation_service._import_class") as mock_import:
        mock_import.return_value = MagicMock(return_value=mock_engine)
        e1 = scheduler.get_engine("wav2lip")
        e2 = scheduler.get_engine("wav2lip")
        assert e1 is e2
        assert mock_import.call_count == 1


def test_model_scheduler_invalid_model():
    scheduler = ModelScheduler()
    with pytest.raises(ValueError, match="不支持的模型"):
        scheduler.get_engine("nonexistent")


def test_model_scheduler_available_models():
    scheduler = ModelScheduler()
    models = scheduler.get_available_models()
    assert len(models) == 3
    names = [m["name"] for m in models]
    assert "wav2lip" in names
    assert "sadtalker" in names
    assert "latentsync" in names
    for m in models:
        assert m["loaded"] is False


def test_model_scheduler_available_models_after_load():
    scheduler = ModelScheduler()
    mock_engine = MagicMock()
    mock_engine.get_model_info.return_value = {"name": "wav2lip", "loaded": True}

    with patch("app.services.generation_service._import_class") as mock_import:
        mock_import.return_value = MagicMock(return_value=mock_engine)
        scheduler.get_engine("wav2lip")

    models = scheduler.get_available_models()
    wav2lip_model = next(m for m in models if m["name"] == "wav2lip")
    assert wav2lip_model["loaded"] is True
