from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from main import app, create_app  # noqa: E402


def _build_client() -> TestClient:
    os.environ.setdefault("DATA_DIR", str(BACKEND_ROOT / "data"))
    os.environ.setdefault("MODELS_DIR", str(BACKEND_ROOT.parent / "models"))
    return TestClient(create_app())


def _is_dml_unavailable(body: dict) -> bool:
    directml = body.get("directml") or {}
    return directml.get("available") is False


def test_create_app_imports() -> None:
    assert app is not None
    assert hasattr(app, "routes")


def test_health_endpoint() -> None:
    client = _build_client()
    response = client.get("/api/v1/health")
    body = response.json()
    assert "request_id" in body
    assert "directml" in body
    assert "providers" in body.get("onnx_provider", {})
    directml = body.get("directml", {})
    assert directml.get("cpu_fallback_enabled") is False
    assert isinstance(body.get("max_upload_mb"), int)
    assert body["max_upload_mb"] >= 50
    assert body.get("max_upload_bytes") == body["max_upload_mb"] * 1024 * 1024
    if _is_dml_unavailable(body):
        assert response.status_code == 503
        assert body.get("status") == "unavailable"
    else:
        assert response.status_code == 200
        assert body.get("status") == "ok"


def test_system_info_endpoint() -> None:
    client = _build_client()
    response = client.get("/api/v1/system/info")
    body = response.json()
    assert "request_id" in body
    assert "gpu" in body
    assert "directml" in body
    assert "providers" in body.get("onnx_provider", {})
    directml = body.get("directml", {})
    assert directml.get("cpu_fallback_enabled") is False
    assert isinstance(body.get("max_upload_mb"), int)
    if _is_dml_unavailable(body):
        assert response.status_code == 503
    else:
        assert response.status_code == 200


def test_engine_status_endpoint() -> None:
    client = _build_client()
    response = client.get("/api/v1/generation/engine/status")
    body = response.json()
    assert "request_id" in body
    assert "directml_available" in body
    assert body.get("cpu_fallback_enabled") is False
    if not body.get("directml_available"):
        assert response.status_code == 503


def test_mounted_routes_present() -> None:
    client = _build_client()
    paths = {route.path for route in client.app.routes}
    assert "/api/v1/health" in paths
    assert "/api/v1/system/info" in paths
    assert "/api/v1/music/upload" in paths
    assert "/api/v1/avatars" in paths
    assert "/api/v1/avatars/upload" in paths
    assert "/api/v1/generation" in paths
    assert "/api/v1/generation/engine/status" in paths


def test_root_endpoint() -> None:
    client = _build_client()
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body.get("api_prefix") == "/api/v1"
