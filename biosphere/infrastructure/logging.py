"""GOV-006 compliant structured logging.

Configures structlog for JSONL output with crash artifact
support. All logging goes through structlog — no print().
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import structlog


def setup_logging(
    *,
    log_dir: str | Path = "logs",
    crash_dir: str | Path = "logs/crashes",
    level: int = logging.INFO,
) -> None:
    """Configure structured logging per GOV-006.

    Sets up:
    - structlog with JSON rendering
    - File handler writing JSONL to log_dir
    - Crash artifact directory for unhandled exceptions
    - Global sys.excepthook for crash capture

    Args:
        log_dir: Directory for general log files.
        crash_dir: Directory for crash artifact JSONL files.
        level: Minimum log level.
    """
    log_path = Path(log_dir)
    crash_path = Path(crash_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    crash_path.mkdir(parents=True, exist_ok=True)

    # Configure stdlib logging as structlog's backend
    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=[
            logging.FileHandler(
                log_path / "biosphere.log",
                mode="a",
                encoding="utf-8",
            ),
            logging.StreamHandler(sys.stderr),
        ],
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Install global exception hook for crash artifacts
    _original_hook = sys.excepthook

    def _crash_hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: Any,
    ) -> None:
        """Write crash artifact as JSONL, then call original hook."""
        _write_crash_artifact(crash_path, exc_type, exc_value)
        _original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _crash_hook


def _write_crash_artifact(
    crash_dir: Path,
    exc_type: type[BaseException],
    exc_value: BaseException,
) -> Path:
    """Write a JSONL crash artifact to the crash directory.

    Args:
        crash_dir: Directory to write crash files.
        exc_type: Exception class.
        exc_value: Exception instance.

    Returns:
        Path to the created crash file.
    """
    import datetime

    timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
    filename = f"crash_{timestamp.strftime('%Y%m%d_%H%M%S')}.jsonl"
    filepath = crash_dir / filename

    record: dict[str, Any] = {
        "event": "unhandled_exception",
        "exception_type": exc_type.__name__,
        "exception_message": str(exc_value),
        "timestamp": timestamp.isoformat(),
    }

    # Include structured context if it's an ApplicationError
    from biosphere.infrastructure.errors import ApplicationError

    if isinstance(exc_value, ApplicationError):
        record["error_context"] = exc_value.to_dict()

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return filepath
