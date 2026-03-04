"""Configuration schema and loader.

Pydantic v2 models that satisfy the SimulationParams protocol
defined in biosphere.core.simulation. Loads from YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator

from biosphere.infrastructure.errors import ConfigurationError


class SimulationConfig(BaseModel):
    """Simulation parameters satisfying SimulationParams protocol.

    All fields have validated ranges matching BLU-002 §2.4.
    Defense-in-depth: both Pydantic and SimulationEngine validate.

    Attributes:
        growth_rate: Logistic growth rate for plants. (0.0, 1.0].
        reproduction_threshold: Minimum energy to reproduce. (0.0, 1.0].
        max_age_prey: Max age in ticks before prey dies. [1, 10_000].
        max_age_predator: Max age in ticks before predator dies. [1, 10_000].
        metabolic_rate: Energy consumed per tick per organism. (0.0, 1.0].
        weather_sigma: Gaussian filter sigma for weather diffusion. [0.0, 10.0].
    """

    growth_rate: float = 0.1
    reproduction_threshold: float = 0.6
    max_age_prey: int = 500
    max_age_predator: int = 300
    metabolic_rate: float = 0.02
    weather_sigma: float = 2.0

    @field_validator("growth_rate")
    @classmethod
    def _validate_growth_rate(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError(f"growth_rate must be in (0.0, 1.0], got {v}")
        return v

    @field_validator("reproduction_threshold")
    @classmethod
    def _validate_reproduction_threshold(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError(
                f"reproduction_threshold must be in (0.0, 1.0], got {v}"
            )
        return v

    @field_validator("max_age_prey")
    @classmethod
    def _validate_max_age_prey(cls, v: int) -> int:
        if not (1 <= v <= 10_000):
            raise ValueError(f"max_age_prey must be in [1, 10000], got {v}")
        return v

    @field_validator("max_age_predator")
    @classmethod
    def _validate_max_age_predator(cls, v: int) -> int:
        if not (1 <= v <= 10_000):
            raise ValueError(
                f"max_age_predator must be in [1, 10000], got {v}"
            )
        return v

    @field_validator("metabolic_rate")
    @classmethod
    def _validate_metabolic_rate(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError(f"metabolic_rate must be in (0.0, 1.0], got {v}")
        return v

    @field_validator("weather_sigma")
    @classmethod
    def _validate_weather_sigma(cls, v: float) -> float:
        if not (0.0 <= v <= 10.0):
            raise ValueError(
                f"weather_sigma must be in [0.0, 10.0], got {v}"
            )
        return v


def load_config(path: str | Path) -> SimulationConfig:
    """Load SimulationConfig from a YAML file.

    Args:
        path: Path to YAML config file.

    Returns:
        Validated SimulationConfig instance.

    Raises:
        ConfigurationError: If file not found or validation fails.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(
            f"Config file not found: {config_path}",
            details={"path": str(config_path)},
        )

    try:
        with open(config_path, encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigurationError(
            f"Invalid YAML in {config_path}: {e}",
            details={"path": str(config_path)},
        ) from e

    try:
        return SimulationConfig(**raw)
    except Exception as e:
        raise ConfigurationError(
            f"Config validation failed: {e}",
            details={"path": str(config_path), "raw": raw},
        ) from e
