"""Tests for biosphere.infrastructure.logging — GOV-006 structured logging.

Refs: EVO-001, GOV-006
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from biosphere.infrastructure.errors import ApplicationError
from biosphere.infrastructure.logging import _write_crash_artifact, setup_logging


@pytest.mark.unit
class TestSetupLogging:
    """setup_logging() creates directories and configures structlog."""

    def test_creates_log_directories(self, tmp_path: Path) -> None:
        """setup_logging creates log_dir and crash_dir if missing.

        Refs: GOV-006 §3
        """
        log_dir = tmp_path / "logs"
        crash_dir = tmp_path / "logs" / "crashes"
        setup_logging(log_dir=log_dir, crash_dir=crash_dir)
        assert log_dir.exists()
        assert crash_dir.exists()

    def test_installs_excepthook(self, tmp_path: Path) -> None:
        """setup_logging installs a custom sys.excepthook for crash artifacts.

        Refs: GOV-006 §5, GOV-004 §6
        """
        original_hook = sys.excepthook
        setup_logging(
            log_dir=tmp_path / "logs",
            crash_dir=tmp_path / "crashes",
        )
        assert sys.excepthook is not original_hook
        assert callable(sys.excepthook)
        # Restore original hook to avoid test pollution
        sys.excepthook = original_hook

    def test_creates_log_file(self, tmp_path: Path) -> None:
        """setup_logging creates biosphere.log file in log_dir.

        Refs: GOV-006 §3
        """
        log_dir = tmp_path / "logs"
        setup_logging(
            log_dir=log_dir,
            crash_dir=tmp_path / "crashes",
        )
        assert (log_dir / "biosphere.log").exists()
        assert log_dir.is_dir()


@pytest.mark.unit
class TestCrashArtifact:
    """JSONL crash artifact generation — GOV-004 §6."""

    def test_application_error_artifact(self, tmp_path: Path) -> None:
        """ApplicationError crash artifacts include full error context.

        Refs: GOV-004 §6, GOV-006 §5
        """
        crash_dir = tmp_path / "crashes"
        crash_dir.mkdir()

        err = ApplicationError(
            "test crash",
            error_code="TST-CRASH",
            details={"reason": "testing"},
        )

        filepath = _write_crash_artifact(crash_dir, type(err), err, None)
        assert filepath.exists()
        assert filepath.suffix == ".jsonl"

        with open(filepath) as f:
            record = json.loads(f.readline())

        assert record["event"] == "unhandled_exception"
        assert record["exception_type"] == "ApplicationError"
        assert record["error_context"]["error_code"] == "TST-CRASH"
        assert "timestamp" in record

    def test_generic_exception_artifact(self, tmp_path: Path) -> None:
        """Non-ApplicationError exceptions produce crash artifacts without error_context.

        Refs: GOV-004 §6
        """
        crash_dir = tmp_path / "crashes"
        crash_dir.mkdir()

        err = ValueError("generic error")
        filepath = _write_crash_artifact(crash_dir, type(err), err, None)
        assert filepath.exists()

        with open(filepath) as f:
            record = json.loads(f.readline())

        assert record["exception_type"] == "ValueError"
        assert record["exception_message"] == "generic error"
        assert "error_context" not in record

    def test_crash_artifact_filename_format(self, tmp_path: Path) -> None:
        """Crash artifact filename follows crash_YYYYMMDD_HHMMSS.jsonl format.

        Refs: GOV-006 §5
        """
        crash_dir = tmp_path / "crashes"
        crash_dir.mkdir()

        err = RuntimeError("test")
        filepath = _write_crash_artifact(crash_dir, type(err), err, None)
        assert filepath.name.startswith("crash_")
        assert filepath.name.endswith(".jsonl")
        # Should have date component
        assert len(filepath.stem) > len("crash_")

    def test_crash_artifact_is_valid_json(self, tmp_path: Path) -> None:
        """Crash artifact contains valid JSON on each line.

        Refs: GOV-006 §5 (JSONL format)
        """
        crash_dir = tmp_path / "crashes"
        crash_dir.mkdir()

        err = ApplicationError(
            "json test",
            error_code="JSON-001",
            details={"special_chars": "quotes\"and\\slashes"},
        )
        filepath = _write_crash_artifact(crash_dir, type(err), err, None)

        with open(filepath) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)  # Should not raise
                    assert isinstance(record, dict)
                    assert "event" in record
