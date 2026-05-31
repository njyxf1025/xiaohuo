from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from app.core.logger import JSONFormatter, get_request_id, new_request_id, set_request_id


def test_json_formatter_basic():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=None,
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["message"] == "test message"
    assert data["level"] == "INFO"
    assert "timestamp" in data
    assert "request_id" in data


def test_json_formatter_with_exception():
    formatter = JSONFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="error occurred",
        args=None,
        exc_info=exc_info,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "ERROR"
    assert "exception" in data
    assert "ValueError" in data["exception"]


def test_request_id_context():
    rid = new_request_id()
    assert get_request_id() == rid

    rid2 = new_request_id()
    assert get_request_id() == rid2
    assert rid != rid2


def test_set_request_id():
    set_request_id("custom-id-123")
    assert get_request_id() == "custom-id-123"


def test_request_id_in_log_output():
    new_request_id()
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="with request id",
        args=None,
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["request_id"] == get_request_id()


@pytest.mark.asyncio
async def test_request_id_in_response_headers(client):
    response = await client.get("/api/health")
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) > 0


@pytest.mark.asyncio
async def test_request_id_different_per_request(client):
    r1 = await client.get("/api/health")
    r2 = await client.get("/api/health")
    id1 = r1.headers.get("X-Request-ID", "")
    id2 = r2.headers.get("X-Request-ID", "")
    assert id1 != id2
