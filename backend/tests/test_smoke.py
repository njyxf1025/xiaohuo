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


def test_create_app_imports() -> None:
    assert app is not None
    assert hasattr(app, "routes")


def test_health_endpoint() -> None:
    client = _build_client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "ok"
    assert "request_id" in body
    assert "onnx_provider" in body
    assert "providers" in body["onnx_provider"]


def test_system_info_endpoint() -> None:
    client = _build_client()
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "request_id" in body
    assert "onnx_provider" in body
    assert "gpu" in body


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
