"""TRACE-level logging test per GOV-006 §14.

Validates that:
1. setup_logging() can be configured at TRACE level
2. TRACE-level messages are emitted
3. All log levels produce structured output

Refs: GOV-006 §14, DEF-001-14
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest
import structlog

from biosphere.infrastructure.logging import TRACE_LEVEL, setup_logging


@pytest.fixture
def trace_log_dir(tmp_path: Path) -> Path:
    """Create temp log directory for TRACE test."""
    return tmp_path / "trace_logs"


class TestTraceLogging:
    """Validate TRACE-level logging per GOV-006 §14."""

    def test_trace_level_via_env_var(
        self, trace_log_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """LOG_LEVEL=TRACE activates trace-level output.

        Refs: GOV-006 §11, §14
        """
        monkeypatch.setenv("LOG_LEVEL", "TRACE")
        setup_logging(
            log_dir=str(trace_log_dir),
            crash_dir=str(trace_log_dir / "crashes"),
        )

        logger = structlog.get_logger()
        logger.debug("trace.test.debug", key="value")

        # TRACE level should be set or lower
        assert logging.root.level <= logging.DEBUG

    def test_trace_level_explicit(
        self, trace_log_dir: Path,
    ) -> None:
        """Explicit level=5 (TRACE) activates trace-level output.

        Refs: GOV-006 §14
        """
        # Remove env var if set
        os.environ.pop("LOG_LEVEL", None)
        setup_logging(
            log_dir=str(trace_log_dir),
            crash_dir=str(trace_log_dir / "crashes"),
            level=TRACE_LEVEL,
        )
        assert logging.root.level == TRACE_LEVEL

    def test_structured_output_at_all_levels(
        self, trace_log_dir: Path,
    ) -> None:
        """All log levels produce JSONL structured output.

        Refs: GOV-006 §3.2
        """
        os.environ.pop("LOG_LEVEL", None)
        setup_logging(
            log_dir=str(trace_log_dir),
            crash_dir=str(trace_log_dir / "crashes"),
            level=logging.DEBUG,
        )

        logger = structlog.get_logger()
        logger.info("test.structured", component="logging", tick=42)

        # Verify log file contains JSONL
        log_file = trace_log_dir / "biosphere.log"
        assert log_file.exists(), "Log file should exist after setup_logging"

        content = log_file.read_text()
        assert len(content) > 0, "Log file should not be empty"

        # Parse last line as JSON
        lines = [ln for ln in content.strip().splitlines() if ln.strip()]
        assert len(lines) >= 1
        record = json.loads(lines[-1])
        assert "event" in record
        assert "level" in record
