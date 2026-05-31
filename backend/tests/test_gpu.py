from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.gpu import GPUManager


@pytest.mark.asyncio
async def test_gpu_info_endpoint(client):
    response = await client.get("/api/gpu/info")
    assert response.status_code == 200
    data = response.json()
    assert "device_type" in data
    assert "device_name" in data
    assert "torch_version" in data


@pytest.mark.asyncio
async def test_gpu_memory_endpoint(client):
    response = await client.get("/api/gpu/memory")
    assert response.status_code == 200
    data = response.json()
    assert "available" in data


def test_gpu_manager_singleton():
    GPUManager._instance = None
    m1 = GPUManager.get_instance()
    m2 = GPUManager.get_instance()
    assert m1 is m2
    GPUManager._instance = None


def test_gpu_manager_cpu_fallback():
    GPUManager._instance = None
    with patch("app.core.gpu.detect_gpu") as mock_detect:
        mock_detect.return_value = {
            "device_type": "cpu",
            "device_name": "CPU",
            "device_index": None,
            "torch_version": "2.0.0",
            "backend_version": None,
        }
        manager = GPUManager()
        assert manager.get_device_info()["device_type"] == "cpu"
        assert manager.is_available() is False
        assert manager.get_memory_info() is None
    GPUManager._instance = None


def test_gpu_manager_rocm_device():
    GPUManager._instance = None
    with patch("app.core.gpu.detect_gpu") as mock_detect:
        mock_detect.return_value = {
            "device_type": "rocm",
            "device_name": "AMD Radeon RX 6700 XT",
            "device_index": 0,
            "torch_version": "2.0.0",
            "backend_version": "5.7",
        }
        manager = GPUManager()
        info = manager.get_device_info()
        assert info["device_type"] == "rocm"
        assert info["device_name"] == "AMD Radeon RX 6700 XT"
        assert manager.is_available() is True
    GPUManager._instance = None


def test_gpu_manager_no_torch():
    GPUManager._instance = None
    with patch("app.core.gpu.detect_gpu") as mock_detect:
        mock_detect.return_value = {
            "device_type": "cpu",
            "device_name": "CPU",
            "device_index": None,
            "torch_version": None,
            "backend_version": None,
        }
        manager = GPUManager()
        assert manager.get_device_info()["device_type"] == "cpu"
        device = manager.get_device()
        assert device is not None
        assert str(device) == "cpu"
    GPUManager._instance = None


def test_detect_gpu_no_torch():
    from app.core.gpu import detect_gpu

    with patch.dict("sys.modules", {"torch": None}):
        with patch("app.core.gpu.detect_gpu") as mock_detect:
            mock_detect.return_value = {
                "device_type": "cpu",
                "device_name": "CPU",
                "device_index": None,
                "torch_version": None,
                "backend_version": None,
            }
            result = detect_gpu()
            assert result["device_type"] == "cpu"


def test_gpu_manager_amd_6700xt_rocm():
    GPUManager._instance = None
    with patch("app.core.gpu.detect_gpu") as mock_detect:
        mock_detect.return_value = {
            "device_type": "rocm",
            "device_name": "AMD Radeon RX 6700 XT",
            "device_index": 0,
            "torch_version": "2.4.0",
            "backend_version": "6.0",
        }
        manager = GPUManager()
        info = manager.get_device_info()
        assert info["device_type"] == "rocm"
        assert "6700" in info["device_name"]
        assert info["backend_version"] == "6.0"
        assert manager.is_available() is True
        device = manager.get_device()
        assert device is not None
        assert device.type == "cuda"
    GPUManager._instance = None


def test_gpu_manager_cuda_device():
    GPUManager._instance = None
    with patch("app.core.gpu.detect_gpu") as mock_detect:
        mock_detect.return_value = {
            "device_type": "cuda",
            "device_name": "NVIDIA GeForce RTX 4090",
            "device_index": 0,
            "torch_version": "2.4.0",
            "backend_version": "12.1",
        }
        manager = GPUManager()
        info = manager.get_device_info()
        assert info["device_type"] == "cuda"
        assert manager.is_available() is True
    GPUManager._instance = None
