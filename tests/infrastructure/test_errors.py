"""Tests for biosphere.infrastructure.errors — GOV-004 compliance.

Refs: EVO-001, GOV-004
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from biosphere.infrastructure.errors import ApplicationError, ConfigurationError


class TestApplicationError:
    """ApplicationError carries structured context."""

    def test_basic_creation(self) -> None:
        """Error has message, default error_code, and correlation_id."""
        err = ApplicationError("something broke")
        assert str(err) == "something broke"
        assert err.error_code == "APP-000"
        assert len(err.correlation_id) == 12

    def test_custom_fields(self) -> None:
        """Custom error_code, details, and correlation_id propagate."""
        err = ApplicationError(
            "bad input",
            error_code="VAL-001",
            details={"field": "growth_rate"},
            correlation_id="test-123",
        )
        assert err.error_code == "VAL-001"
        assert err.details == {"field": "growth_rate"}
        assert err.correlation_id == "test-123"

    def test_to_dict_roundtrip(self) -> None:
        """to_dict() produces JSON-serializable dict with all fields."""
        err = ApplicationError(
            "test error",
            error_code="TST-001",
            details={"key": "value"},
        )
        d = err.to_dict()
        # Must be JSON-serializable
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["error_type"] == "ApplicationError"
        assert parsed["error_code"] == "TST-001"
        assert parsed["message"] == "test error"
        assert "timestamp" in parsed

    def test_timestamp_is_utc(self) -> None:
        """Timestamp is timezone-aware UTC."""
        import datetime

        err = ApplicationError("test")
        assert err.timestamp.tzinfo == datetime.timezone.utc


class TestConfigurationError:
    """ConfigurationError is a specialized ApplicationError."""

    def test_inherits_application_error(self) -> None:
        """ConfigurationError IS-A ApplicationError."""
        err = ConfigurationError("invalid config")
        assert isinstance(err, ApplicationError)
        assert isinstance(err, Exception)

    def test_default_error_code(self) -> None:
        """Default error_code is CFG-001."""
        err = ConfigurationError("missing file")
        assert err.error_code == "CFG-001"

    def test_can_be_caught_as_application_error(self) -> None:
        """Catching ApplicationError catches ConfigurationError."""
        with pytest.raises(ApplicationError):
            raise ConfigurationError("test")


class TestCrashArtifact:
    """JSONL crash artifact generation via sys.excepthook."""

    def test_crash_artifact_written(self, tmp_path: Path) -> None:
        """_write_crash_artifact produces valid JSONL file."""
        from biosphere.infrastructure.logging import _write_crash_artifact

        crash_dir = tmp_path / "crashes"
        crash_dir.mkdir()

        err = ApplicationError(
            "test crash",
            error_code="TST-CRASH",
            details={"reason": "testing"},
        )

        filepath = _write_crash_artifact(crash_dir, type(err), err)
        assert filepath.exists()

        with open(filepath) as f:
            record = json.loads(f.readline())

        assert record["event"] == "unhandled_exception"
        assert record["exception_type"] == "ApplicationError"
        assert record["error_context"]["error_code"] == "TST-CRASH"
