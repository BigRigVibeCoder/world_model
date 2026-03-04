"""GOV-004 compliant error hierarchy.

Provides structured error handling with correlation IDs,
error codes, timestamps, and JSONL crash artifact support.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any


class ApplicationError(Exception):
    """Base error for all application-level failures.

    Carries structured context for GOV-004 compliance:
    correlation_id, error_code, timestamp, and arbitrary details.

    Example:
        raise ApplicationError(
            "Config file not found",
            error_code="CFG-001",
            details={"path": "/config/simulation.yaml"},
        )
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "APP-000",
        details: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.correlation_id = correlation_id or uuid.uuid4().hex[:12]
        self.timestamp = datetime.datetime.now(tz=datetime.timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSONL logging."""
        return {
            "error_type": type(self).__name__,
            "error_code": self.error_code,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class ConfigurationError(ApplicationError):
    """Raised when configuration loading or validation fails.

    Examples: missing YAML file, invalid parameter ranges,
    schema validation failure.
    """

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="CFG-001",
            details=details,
            correlation_id=correlation_id,
        )
