from __future__ import annotations

import logging
import sys
from logging.config import dictConfig
from typing import Any

from pythonjsonlogger import jsonlogger

from .config import get_settings
from .request_id import request_id_ctx


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.request_id = request_id_ctx.get()
        except LookupError:
            record.request_id = "-"
        if not hasattr(record, "stage"):
            record.stage = "-"
        if not hasattr(record, "duration_ms"):
            record.duration_ms = "-"
        return True


class _JsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("logger", record.name)
        log_record.setdefault("stage", getattr(record, "stage", "-"))
        log_record.setdefault("duration_ms", getattr(record, "duration_ms", "-"))
        log_record.setdefault("request_id", getattr(record, "request_id", "-"))


def configure_logging() -> None:
    settings = get_settings()
    level = settings.log_level.upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "context": {
                    "()": "core.logging.ContextFilter",
                }
            },
            "formatters": {
                "json": {
                    "()": "core.logging._JsonFormatter",
                    "fmt": "%(asctime)s %(level)s %(logger)s %(message)s %(request_id)s %(stage)s %(duration_ms)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "json",
                    "filters": ["context"],
                }
            },
            "loggers": {
                "": {
                    "handlers": ["stdout"],
                    "level": level,
                    "propagate": False,
                },
                "uvicorn": {
                    "handlers": ["stdout"],
                    "level": level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["stdout"],
                    "level": level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["stdout"],
                    "level": level,
                    "propagate": False,
                },
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
