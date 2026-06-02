from __future__ import annotations

import time
import uuid
from contextvars import ContextVar
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logging import get_logger

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    try:
        return request_id_ctx.get()
    except LookupError:
        return "-"


def set_request_id(value: str) -> None:
    request_id_ctx.set(value)


def new_request_id() -> str:
    return uuid.uuid4().hex


class RequestIDMiddleware(BaseHTTPMiddleware):
    HEADER = "X-Request-ID"

    def __init__(self, app, header: str = HEADER) -> None:
        super().__init__(app)
        self.header = header
        self._logger = get_logger("core.request_id")

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get(self.header)
        rid = incoming if incoming else new_request_id()
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
            self._logger.exception(
                "request failed",
                extra={"stage": "request", "duration_ms": duration_ms},
            )
            raise
        finally:
            request_id_ctx.reset(token)
        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
        response.headers[self.header] = rid
        self._logger.info(
            "request handled",
            extra={
                "stage": "request",
                "duration_ms": duration_ms,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response
