"""Tests for biosphere.infrastructure.errors — GOV-004 compliance.

Refs: EVO-001, GOV-004, BLU-002 §4
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from biosphere.infrastructure.errors import ApplicationError, ConfigurationError


@pytest.mark.unit
class TestApplicationError:
    """ApplicationError carries structured context for GOV-004."""

    def test_basic_creation(self) -> None:
        """Error has message, default error_code, and auto-generated correlation_id.

        Refs: GOV-004 §8 (correlation IDs)
        """
        err = ApplicationError("something broke")
        assert str(err) == "something broke"
        assert err.error_code == "APP-000"
        assert len(err.correlation_id) == 12
        assert err.message == "something broke"

    def test_custom_fields(self) -> None:
        """Custom error_code, details, and correlation_id propagate correctly.

        Refs: GOV-004 §3 (error taxonomy)
        """
        err = ApplicationError(
            "bad input",
            error_code="VAL-001",
            details={"field": "growth_rate"},
            correlation_id="test-123",
        )
        assert err.error_code == "VAL-001"
        assert err.details == {"field": "growth_rate"}
        assert err.correlation_id == "test-123"
        assert err.message == "bad input"

    def test_to_dict_roundtrip(self) -> None:
        """to_dict() produces JSON-serializable dict with all required fields.

        Refs: GOV-004 §6 (crash artifacts)
        """
        err = ApplicationError(
            "test error",
            error_code="TST-001",
            details={"key": "value"},
        )
        d = err.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["error_type"] == "ApplicationError"
        assert parsed["error_code"] == "TST-001"
        assert parsed["message"] == "test error"
        assert "timestamp" in parsed
        assert "correlation_id" in parsed

    def test_timestamp_is_utc(self) -> None:
        """Timestamp is timezone-aware UTC per GOV-006 timestamp requirements.

        Refs: GOV-006 §3 (timestamp format)
        """
        import datetime

        err = ApplicationError("test")
        assert err.timestamp.tzinfo == datetime.UTC
        assert err.timestamp.year >= 2026

    def test_details_default_empty(self) -> None:
        """Details defaults to empty dict, not None.

        Refs: GOV-004 §3
        """
        err = ApplicationError("test")
        assert err.details == {}
        assert isinstance(err.details, dict)

    def test_is_exception_subclass(self) -> None:
        """ApplicationError IS-A Exception (catchable by generic handler).

        Refs: GOV-004 §2 (error hierarchy)
        """
        err = ApplicationError("test")
        assert isinstance(err, Exception)
        assert isinstance(err, ApplicationError)


@pytest.mark.unit
class TestConfigurationError:
    """ConfigurationError is a specialized ApplicationError for config failures."""

    def test_inherits_application_error(self) -> None:
        """ConfigurationError IS-A ApplicationError.

        Refs: GOV-004 §2 (error taxonomy)
        """
        err = ConfigurationError("invalid config")
        assert isinstance(err, ApplicationError)
        assert isinstance(err, Exception)
        assert err.error_code == "CFG-001"

    def test_default_error_code(self) -> None:
        """Default error_code is CFG-001 with valid correlation ID.

        Refs: GOV-004 §3 (error codes)
        """
        err = ConfigurationError("missing file")
        assert err.error_code == "CFG-001"
        assert len(err.correlation_id) == 12

    def test_can_be_caught_as_application_error(self) -> None:
        """Catching ApplicationError catches ConfigurationError (Liskov).

        Refs: GOV-004 §2 (hierarchy)
        """
        with pytest.raises(ApplicationError) as exc_info:
            raise ConfigurationError("test")
        assert exc_info.value.error_code == "CFG-001"
        assert str(exc_info.value) == "test"

    def test_custom_details_propagate(self) -> None:
        """Custom details and correlation_id propagate through inheritance.

        Refs: GOV-004 §8 (correlation IDs)
        """
        err = ConfigurationError(
            "bad yaml",
            details={"path": "/config/sim.yaml"},
            correlation_id="cfg-test-001",
        )
        assert err.details["path"] == "/config/sim.yaml"
        assert err.correlation_id == "cfg-test-001"


@pytest.mark.unit
class TestCrashArtifact:
    """JSONL crash artifact generation — GOV-004 §6."""

    def test_crash_artifact_written(self, tmp_path: Path) -> None:
        """_write_crash_artifact produces valid JSONL file with required fields.

        Refs: GOV-004 §6, GOV-006 §5 (JSONL format)
        """
        from biosphere.infrastructure.logging import _write_crash_artifact

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

    def test_crash_artifact_for_generic_exception(self, tmp_path: Path) -> None:
        """Non-ApplicationError exceptions still produce crash artifacts.

        Refs: GOV-004 §6
        """
        from biosphere.infrastructure.logging import _write_crash_artifact

        crash_dir = tmp_path / "crashes"
        crash_dir.mkdir()

        err = ValueError("generic error")
        filepath = _write_crash_artifact(crash_dir, type(err), err, None)
        assert filepath.exists()

        with open(filepath) as f:
            record = json.loads(f.readline())

        assert record["exception_type"] == "ValueError"
        assert "error_context" not in record
