"""GOV-004 compliant error hierarchy.

Provides structured error handling with correlation IDs,
error categories, error codes, timestamps, and JSONL crash
artifact support.

GOV-004 §2: Error taxonomy with category classification.
GOV-004 §3: Structured ErrorContext on every exception.
GOV-004 §8: Correlation ID propagation.
"""

from __future__ import annotations

import datetime
import uuid
from enum import Enum, auto
from typing import Any


class ErrorCategory(Enum):
    """Error taxonomy per GOV-004 §2.

    Drives automated recovery decisions.

    Refs: GOV-004 §2
    """

    VALIDATION = auto()
    BUSINESS_LOGIC = auto()
    EXTERNAL_SERVICE = auto()
    DATABASE = auto()
    RESOURCE = auto()
    INFRASTRUCTURE = auto()
    CONFIGURATION = auto()
    NETWORK = auto()
    SECURITY = auto()
    HARDWARE = auto()
    FATAL = auto()
    TRANSIENT = auto()
    UNKNOWN = auto()


class ApplicationError(Exception):
    """Base error for all application-level failures.

    Carries structured context for GOV-004 compliance:
    correlation_id, error_code, category, timestamp, and
    arbitrary details.

    Example:
        raise ApplicationError(
            "Config file not found",
            error_code="CFG-001",
            category=ErrorCategory.CONFIGURATION,
            details={"path": "/config/simulation.yaml"},
        )

    Refs: GOV-004 §3
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "APP-000",
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        details: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.details = details or {}
        self.correlation_id: str = kwargs.get(
            "correlation_id",
        ) or uuid.uuid4().hex[:12]
        self.timestamp = datetime.datetime.now(tz=datetime.UTC)
        self.retryable: bool = kwargs.get("retryable", False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSONL logging.

        Refs: GOV-004 §3
        """
        return {
            "error_type": type(self).__name__,
            "error_code": self.error_code,
            "category": self.category.name,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "retryable": self.retryable,
        }


class ConfigurationError(ApplicationError):
    """Raised when configuration loading or validation fails.

    Examples: missing YAML file, invalid parameter ranges,
    schema validation failure.

    Refs: GOV-004 §2 (CONFIGURATION category)
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
            category=ErrorCategory.CONFIGURATION,
            details=details,
            correlation_id=correlation_id,
        )


class SimulationError(ApplicationError):
    """Raised when the simulation engine encounters an unrecoverable state.

    Examples: double NaN rollback, invalid state grid.

    Refs: GOV-004 §2 (FATAL category)
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
            error_code="SIM-001",
            category=ErrorCategory.FATAL,
            details=details,
            correlation_id=correlation_id,
        )


class TrainingError(ApplicationError):
    """Raised when RL training encounters an error.

    Examples: checkpoint save failure, invalid config.

    Refs: GOV-004 §2 (RESOURCE category)
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
            error_code="TRN-001",
            category=ErrorCategory.RESOURCE,
            details=details,
            correlation_id=correlation_id,
        )
