"""Tests for biosphere.infrastructure.config — Pydantic config schema and YAML loader.

Refs: EVO-001 §4.1, BLU-002 §2.4, GOV-004
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §5: Hypothesis property tests for validators.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from biosphere.infrastructure.config import SimulationConfig, load_config
from biosphere.infrastructure.errors import ConfigurationError


@pytest.mark.unit
class TestSimulationConfigDefaults:
    """Default SimulationConfig values match BLU-002 §2.4."""

    def test_defaults_match_blueprint(self) -> None:
        """All default values match BLU-001 §7.1 specification.

        Refs: BLU-001 §7.1, BLU-002 §2.4
        """
        config = SimulationConfig()
        assert config.growth_rate == 0.1
        assert config.reproduction_threshold == 0.6
        assert config.max_age_prey == 500
        assert config.max_age_predator == 300
        assert config.metabolic_rate == 0.02
        assert config.weather_sigma == 2.0


@pytest.mark.unit
class TestSimulationConfigValidation:
    """Field validators enforce BLU-002 §2.4 ranges."""

    @pytest.mark.parametrize(
        "field,value",
        [
            ("growth_rate", 0.0),
            ("growth_rate", -0.1),
            ("growth_rate", 1.5),
            ("reproduction_threshold", 0.0),
            ("reproduction_threshold", 1.5),
            ("max_age_prey", 0),
            ("max_age_prey", 10_001),
            ("max_age_predator", 0),
            ("max_age_predator", 10_001),
            ("metabolic_rate", 0.0),
            ("metabolic_rate", 1.5),
            ("weather_sigma", -0.1),
            ("weather_sigma", 10.5),
        ],
    )
    def test_invalid_field_raises_validation_error(
        self, field: str, value: float | int,
    ) -> None:
        """Out-of-range field values raise Pydantic ValidationError.

        Refs: BLU-002 §2.4
        """
        with pytest.raises(ValidationError) as exc_info:
            SimulationConfig(**{field: value})
        assert field in str(exc_info.value)

    @pytest.mark.parametrize(
        "field,value",
        [
            ("growth_rate", 0.01),
            ("growth_rate", 1.0),
            ("reproduction_threshold", 0.01),
            ("reproduction_threshold", 1.0),
            ("max_age_prey", 1),
            ("max_age_prey", 10_000),
            ("max_age_predator", 1),
            ("max_age_predator", 10_000),
            ("metabolic_rate", 0.001),
            ("metabolic_rate", 1.0),
            ("weather_sigma", 0.0),
            ("weather_sigma", 10.0),
        ],
    )
    def test_boundary_values_accepted(
        self, field: str, value: float | int,
    ) -> None:
        """Boundary values at range limits are accepted.

        Refs: BLU-002 §2.4
        """
        config = SimulationConfig(**{field: value})
        assert getattr(config, field) == value
        assert isinstance(config, SimulationConfig)


@pytest.mark.property
class TestSimulationConfigPropertyBased:
    """Hypothesis tests for config validators.

    GOV-002 §5: Property-based testing for all validation functions.
    """

    @given(
        growth_rate=st.floats(min_value=0.01, max_value=1.0),
        weather_sigma=st.floats(min_value=0.0, max_value=10.0),
    )
    @settings(max_examples=50, deadline=5000)
    def test_valid_floats_always_accepted(
        self, growth_rate: float, weather_sigma: float,
    ) -> None:
        """Any float within valid range creates a valid config.

        Refs: BLU-002 §2.4, GOV-002 §5
        """
        config = SimulationConfig(
            growth_rate=growth_rate,
            weather_sigma=weather_sigma,
        )
        assert config.growth_rate == growth_rate
        assert config.weather_sigma == weather_sigma

    @given(value=st.floats(min_value=1.01, max_value=1e10))
    @settings(max_examples=20, deadline=5000)
    def test_growth_rate_above_1_always_rejected(self, value: float) -> None:
        """Any growth_rate > 1.0 is always rejected.

        Refs: BLU-002 §2.4, GOV-002 §5
        """
        with pytest.raises(ValidationError):
            SimulationConfig(growth_rate=value)
        assert value > 1.0


@pytest.mark.unit
class TestLoadConfig:
    """YAML config loader — GOV-004 error handling."""

    def test_load_valid_yaml(self) -> None:
        """load_config successfully loads config/simulation.yaml.

        Refs: EVO-001 §4.1
        """
        config = load_config("config/simulation.yaml")
        assert isinstance(config, SimulationConfig)
        assert config.growth_rate == 0.1

    def test_missing_file_raises_configuration_error(self) -> None:
        """Missing file raises ConfigurationError with path details.

        Refs: GOV-004 §3, GOV-004 §8
        """
        with pytest.raises(ConfigurationError) as exc_info:
            load_config("nonexistent/config.yaml")
        assert "not found" in str(exc_info.value)
        assert exc_info.value.error_code == "CFG-001"

    def test_invalid_yaml_raises_configuration_error(
        self, tmp_path: Path,
    ) -> None:
        """Malformed YAML raises ConfigurationError.

        Refs: GOV-004 §3
        """
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("growth_rate: [unclosed bracket")

        with pytest.raises(ConfigurationError) as exc_info:
            load_config(bad_yaml)
        assert "Invalid YAML" in str(exc_info.value)
        assert exc_info.value.error_code == "CFG-001"

    def test_invalid_values_raises_configuration_error(
        self, tmp_path: Path,
    ) -> None:
        """Valid YAML with out-of-range values raises ConfigurationError.

        Refs: GOV-004 §3, BLU-002 §2.4
        """
        invalid_values = tmp_path / "invalid.yaml"
        invalid_values.write_text("growth_rate: 999.0\n")

        with pytest.raises(ConfigurationError) as exc_info:
            load_config(invalid_values)
        assert "validation failed" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "CFG-001"

    def test_empty_yaml_uses_defaults(self, tmp_path: Path) -> None:
        """Empty YAML file results in all-defaults config.

        Refs: BLU-002 §2.4
        """
        empty = tmp_path / "empty.yaml"
        empty.write_text("")

        config = load_config(empty)
        assert config.growth_rate == 0.1
        assert config.metabolic_rate == 0.02

    def test_partial_yaml_merges_with_defaults(self, tmp_path: Path) -> None:
        """Partial YAML overrides only specified fields.

        Refs: BLU-002 §2.4
        """
        partial = tmp_path / "partial.yaml"
        partial.write_text("growth_rate: 0.5\nweather_sigma: 5.0\n")

        config = load_config(partial)
        assert config.growth_rate == 0.5
        assert config.weather_sigma == 5.0
        assert config.metabolic_rate == 0.02  # default
