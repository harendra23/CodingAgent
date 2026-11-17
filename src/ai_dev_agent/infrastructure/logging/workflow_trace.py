import hashlib
import json
import logging
import os
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import RLock
from typing import Any

from dotenv import dotenv_values

TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")

_LOGGERS: dict[Path, logging.Logger] = {}
_LOGGER_LOCK = RLock()
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+\S+"),
    re.compile(r"(?i)(github_pat_|gh[pousr]_)[A-Za-z0-9_]+"),
    re.compile(
        r"(?i)(api[_-]?key|api[_-]?token|access[_-]?token|password|secret|authorization|"
           r"github[_-]?token|"
        r"x-access-token)(\s*[:=]\s*)[^\s,;]+"
    ),
    re.compile(r"(https?://)[^/@\s:]+:[^/@\s]+@"),
)


def _redact(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(r"\1\2[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted[:1000]


def redact_trace_text(value: str) -> str:
    return _redact(value)


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "run_id": record.workflow_run_id,
            "step_order": record.workflow_step_order,
            "step_id": record.workflow_step_id,
            "step": record.workflow_step_name,
            "status": record.workflow_status,
        }
        if record.workflow_error_type:
            event["error_type"] = record.workflow_error_type
            event["error_description"] = _redact(record.workflow_error_description)
        return json.dumps(event, ensure_ascii=False)


def _logger_for(log_path: str | Path | None) -> logging.Logger:
    configured_path = (
        log_path
        or os.environ.get("WORKFLOW_TRACE_LOG_PATH")
        or dotenv_values().get("WORKFLOW_TRACE_LOG_PATH")
        or "logs/workflow-trace.jsonl"
    )
    path = Path(configured_path).expanduser().resolve()
    with _LOGGER_LOCK:
        existing = _LOGGERS.get(path)
        if existing is not None:
            return existing

        path.parent.mkdir(parents=True, exist_ok=True)
        path_hash = hashlib.sha256(str(path).encode()).hexdigest()[:12]
        logger = logging.getLogger(f"ai_dev_agent.workflow.trace.{path_hash}")
        logger.setLevel(TRACE_LEVEL)
        logger.propagate = False
        handler = RotatingFileHandler(
            path,
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setLevel(TRACE_LEVEL)
        handler.setFormatter(_JsonLineFormatter())
        logger.addHandler(handler)
        _LOGGERS[path] = logger
        return logger


class WorkflowTrace:
    def __init__(self, run_id: str, log_path: str | Path | None = None) -> None:
        self._run_id = run_id
        self._logger = _logger_for(log_path)

    def record(
        self,
        *,
        step_order: int,
        step_id: str,
        step_name: str,
        status: str,
        error: BaseException | None = None,
    ) -> None:
        error_type = type(error).__name__ if error is not None else None
        error_description = _redact(str(error)) if error is not None else None
        self._logger.log(
            TRACE_LEVEL,
            "workflow step %s",
            status,
            extra={
                "workflow_run_id": self._run_id,
                "workflow_step_order": step_order,
                "workflow_step_id": step_id,
                "workflow_step_name": step_name,
                "workflow_status": status,
                "workflow_error_type": error_type,
                "workflow_error_description": error_description,
            },
        )
