"""Crash artifact E2E test per GOV-004 §6.

Validates the full crash pipeline:
  sys.excepthook → _write_crash_artifact → parseable JSONL file

Refs: GOV-004 §4, §6, DEF-001-16
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


class TestCrashArtifactPipeline:
    """End-to-end crash artifact generation tests."""

    def test_crash_artifact_generated_on_unhandled_exception(
        self, tmp_path: Path,
    ) -> None:
        """Unhandled exception triggers crash artifact JSONL file.

        Refs: GOV-004 §4, DEF-001-16
        """
        crash_dir = tmp_path / "crashes"
        log_dir = tmp_path / "logs"

        # Run a subprocess that sets up logging and then raises
        script = f'''
import sys
sys.path.insert(0, ".")
from biosphere.infrastructure.logging import setup_logging
setup_logging(
    log_dir="{log_dir}",
    crash_dir="{crash_dir}",
)
raise RuntimeError("deliberate test crash")
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parents[2]),
            timeout=10,
        )

        # Process should fail (unhandled exception)
        assert result.returncode != 0

        # Crash directory should exist with at least one file
        assert crash_dir.exists(), "Crash dir should be created"
        crash_files = list(crash_dir.glob("crash_*.jsonl"))
        assert len(crash_files) >= 1, f"Expected crash file, got: {list(crash_dir.iterdir())}"

        # Parse the crash artifact
        crash_content = crash_files[0].read_text()
        assert len(crash_content) > 0, "Crash file should not be empty"

        record = json.loads(crash_content)
        assert record["exception_type"] == "RuntimeError"
        assert "deliberate test crash" in record["exception_message"]
        assert "stack_trace" in record
        assert len(record["stack_trace"]) > 0

    def test_crash_artifact_contains_required_fields(
        self, tmp_path: Path,
    ) -> None:
        """Crash artifact JSONL has all GOV-004 required fields.

        Refs: GOV-004 §4.2
        """
        crash_dir = tmp_path / "crashes"
        log_dir = tmp_path / "logs"

        script = f'''
import sys
sys.path.insert(0, ".")
from biosphere.infrastructure.logging import setup_logging
setup_logging(
    log_dir="{log_dir}",
    crash_dir="{crash_dir}",
)
raise ValueError("field validation test")
'''
        subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parents[2]),
            timeout=10,
        )

        crash_files = list(crash_dir.glob("crash_*.jsonl"))
        assert len(crash_files) >= 1

        record = json.loads(crash_files[0].read_text())

        # GOV-004 §4.2 required fields
        required_fields = [
            "timestamp", "exception_type", "exception_message", "stack_trace",
        ]
        for field in required_fields:
            assert field in record, f"Missing required field: {field}"
