"""GOV-006 compliant structured logging.

Configures structlog for JSONL output with crash artifact
support. All logging goes through structlog — no print().

GOV-006 §1: Structured only (JSON).
GOV-006 §4: Logs to persistent storage (JSONL file).
GOV-006 §5: structlog with @trace_execution decorator.
GOV-006 §8: Correlation ID in every log via contextvars.
GOV-006 §11: LOG_LEVEL environment variable override.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
import time
import traceback
from collections.abc import Callable, MutableMapping
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import structlog

# ── GOV-004 §8: Correlation ID ContextVar ────────────────────────────────────

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

SERVICE_NAME = "biosphere"


def get_correlation_id() -> str:
    """Get current correlation ID, generate if missing.

    GOV-004 §8: Every request gets a correlation ID.

    Refs: GOV-004 §8
    """
    import uuid

    cid = _correlation_id.get()
    if not cid:
        cid = f"req-{uuid.uuid4().hex[:12]}"
        _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current context.

    Refs: GOV-004 §8
    """
    _correlation_id.set(cid)


# ── GOV-006 §5.1: Structlog Setup ────────────────────────────────────────────


def _add_service_name(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Add service name to every log record.

    Refs: GOV-006 §3.1
    """
    event_dict["service"] = SERVICE_NAME
    # Inject correlation ID
    cid = _correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def _resolve_log_level(level: int | None) -> int:
    """Resolve effective log level from env var or explicit param.

    Priority: LOG_LEVEL env var > explicit `level` arg > INFO default.
    Refs: GOV-006 §11
    """
    env_level = os.environ.get("LOG_LEVEL", "").upper()
    level_map = {
        "TRACE": 5,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "FATAL": logging.CRITICAL,
        "CRITICAL": logging.CRITICAL,
    }
    if env_level and env_level in level_map:
        return level_map[env_level]
    if level is not None:
        return level
    return logging.INFO


def _configure_structlog(resolved_level: int) -> None:
    """Configure structlog processors and binding.

    Refs: GOV-006 §5.1
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _add_service_name,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def setup_logging(
    *,
    service_name: str = "biosphere",
    log_dir: str | Path = "logs",
    crash_dir: str | Path = "logs/crashes",
    level: int | None = None,
) -> None:
    """Configure structured logging per GOV-006.

    Sets up structlog with JSON rendering, file handler, crash artifacts,
    and LOG_LEVEL env var override.

    Refs: GOV-006 §5.1, §11
    """
    global SERVICE_NAME
    SERVICE_NAME = service_name

    resolved_level = _resolve_log_level(level)

    log_path = Path(log_dir)
    crash_path = Path(crash_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    crash_path.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        format="%(message)s",
        level=resolved_level,
        handlers=[
            logging.FileHandler(
                log_path / "biosphere.log",
                mode="a",
                encoding="utf-8",
            ),
            logging.StreamHandler(sys.stderr),
        ],
        force=True,
    )

    _configure_structlog(resolved_level)

    # Install global exception hook for crash artifacts (GOV-004 §4)
    _original_hook = sys.excepthook

    def _crash_hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: Any,
    ) -> None:
        """Write crash artifact as JSONL, then call original hook."""
        _write_crash_artifact(crash_path, exc_type, exc_value, exc_tb)
        _original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _crash_hook


def get_logger(**initial_values: Any) -> Any:
    """Get a structlog logger instance.

    Convenience function for modules to get a logger.
    Uses structlog.get_logger() but ensures service context.

    Refs: GOV-006 §5.2
    """
    return structlog.get_logger(**initial_values)


# ── GOV-006 §5.3: @trace_execution Decorator ─────────────────────────────────

def trace_execution[F: Callable[..., Any]](func: F) -> F:
    """Decorator that logs function entry, exit, and exceptions at DEBUG level.

    Zero-boilerplate trace instrumentation per GOV-006 §5.3.
    Logs: function name, argument count, elapsed_ms, success/failure.

    Refs: GOV-006 §5.3, §8.1
    """
    logger = structlog.get_logger()

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Tracing wrapper — logs entry/exit/exception for the decorated function."""
        func_name = f"{func.__module__}.{func.__qualname__}"
        logger.debug(
            f"{func_name}.enter",
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()),
        )
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            logger.debug(
                f"{func_name}.exit",
                elapsed_ms=round(elapsed, 2),
                success=True,
            )
            return result
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                f"{func_name}.exception",
                elapsed_ms=round(elapsed, 2),
                error=str(e),
                exc_info=True,
            )
            raise

    return wrapper  # type: ignore[return-value]


# ── GOV-004 §6: Crash Artifacts ──────────────────────────────────────────────


def _write_crash_artifact(
    crash_dir: Path,
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: Any,
) -> Path:
    """Write a JSONL crash artifact with full stack trace.

    GOV-004 §6: Required fields: timestamp, error_id, category,
    message, stack_trace, system_state.

    Args:
        crash_dir: Directory to write crash files.
        exc_type: Exception class.
        exc_value: Exception instance.
        exc_tb: Traceback object.

    Returns:
        Path to the created crash file.

    Refs: GOV-004 §6
    """
    import datetime

    timestamp = datetime.datetime.now(tz=datetime.UTC)
    filename = f"crash_{timestamp.strftime('%Y%m%d_%H%M%S')}.jsonl"
    filepath = crash_dir / filename

    # GOV-004 §6.1: full stack trace
    stack_trace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    record: dict[str, Any] = {
        "event": "unhandled_exception",
        "level": "FATAL",
        "service": SERVICE_NAME,
        "exception_type": exc_type.__name__,
        "exception_message": str(exc_value),
        "stack_trace": stack_trace,
        "timestamp": timestamp.isoformat(),
        "correlation_id": _correlation_id.get() or "none",
    }

    # Include structured context if it's an ApplicationError
    from biosphere.infrastructure.errors import ApplicationError

    if isinstance(exc_value, ApplicationError):
        record["error_context"] = exc_value.to_dict()

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return filepath
