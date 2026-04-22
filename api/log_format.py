"""Structured JSON log formatter -- stdlib logging only, no new deps (DATA-04).

Emits one JSON object per log record. Extra context is flattened to top level
so jq/grep queries on log files work without nested accessors.

Usage:
    from api.log_format import install_json_logging
    install_json_logging()  # root logger -> JSON

    # Daemon-specific logger:
    install_json_logging(logger_name="investment_daemon")
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

# Fields populated by stdlib LogRecord -- never promoted as "extras"
_STANDARD_FIELDS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Emit a single-line JSON object for each log record.

    Mandatory keys: timestamp (ISO 8601 UTC), level, logger, message.
    User extras are flattened to top level for grep-ability.
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload: dict = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),  # interpolates % args
        }
        # Flatten user-supplied extras (skip stdlib internals and private attrs)
        for key, val in record.__dict__.items():
            if key not in _STANDARD_FIELDS and not key.startswith("_"):
                try:
                    json.dumps(val)
                    payload[key] = val
                except (TypeError, ValueError):
                    payload[key] = repr(val)
        # Capture exception traceback if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def install_json_logging(
    level: int = logging.INFO,
    logger_name: str | None = None,
) -> logging.Logger:
    """Replace all handlers on the target logger with a single StreamHandler emitting JSON.

    Args:
        level: Log level to set on the logger.
        logger_name: Logger name. None = root logger (for API). Pass
            ``"investment_daemon"`` for the daemon logger.

    Returns:
        The configured logger.

    Note:
        Clearing root-logger handlers does NOT affect ``uvicorn.access`` and
        ``uvicorn.error`` loggers because they are named loggers with
        ``propagate=False`` after uvicorn configures them. This function is
        safe to call before uvicorn starts.
    """
    import sys

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    # Clear existing handlers to avoid double-emission
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger
