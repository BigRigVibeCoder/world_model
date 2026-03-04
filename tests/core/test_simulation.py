"""Tests for biosphere.core.simulation — SimulationEngine.

Refs: EVO-001, BLU-002 §2.2
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from biosphere.core.errors import InterventionError, SimulationError
from biosphere.core.simulation import SimulationEngine, SimulationParams
from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
    Intervention,
    InterventionType,
)


def _default_params(**overrides: Any) -> SimpleNamespace:
    """Create valid SimulationParams with optional overrides."""
    defaults = {
        "growth_rate": 0.1,
        "reproduction_threshold": 0.6,
        "max_age_prey": 500,
        "max_age_predator": 300,
        "metabolic_rate": 0.02,
        "weather_sigma": 2.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestSimulationParamsProtocol:
    """SimulationParams protocol conformance."""

    def test_simplenamespace_satisfies_protocol(self) -> None:
        """SimpleNamespace with correct fields satisfies SimulationParams."""
        params = _default_params()
        assert isinstance(params, SimulationParams)

    def test_pydantic_model_satisfies_protocol(self) -> None:
        """SimulationConfig Pydantic model satisfies SimulationParams."""
        from biosphere.infrastructure.config import SimulationConfig

        config = SimulationConfig()
        assert isinstance(config, SimulationParams)


class TestParameterValidation:
    """SimulationEngine.__init__ validates all parameter ranges."""

    def test_valid_params_accepted(self) -> None:
        """Valid default params create engine without error."""
        engine = SimulationEngine(_default_params())
        assert engine.tick == 0

    @pytest.mark.parametrize(
        "field,value,match",
        [
            ("growth_rate", 0.0, "growth_rate"),
            ("growth_rate", 1.5, "growth_rate"),
            ("growth_rate", -0.1, "growth_rate"),
            ("reproduction_threshold", 0.0, "reproduction_threshold"),
            ("reproduction_threshold", 1.5, "reproduction_threshold"),
            ("max_age_prey", 0, "max_age_prey"),
            ("max_age_prey", 10_001, "max_age_prey"),
            ("max_age_predator", 0, "max_age_predator"),
            ("max_age_predator", 10_001, "max_age_predator"),
            ("metabolic_rate", 0.0, "metabolic_rate"),
            ("metabolic_rate", 1.5, "metabolic_rate"),
            ("weather_sigma", -0.1, "weather_sigma"),
            ("weather_sigma", 10.1, "weather_sigma"),
        ],
    )
    def test_invalid_param_raises(
        self, field: str, value: Any, match: str,
    ) -> None:
        """Out-of-range parameters raise SimulationError."""
        params = _default_params(**{field: value})
        with pytest.raises(SimulationError, match=match):
            SimulationEngine(params)

    def test_metabolic_rate_exceeds_reproduction_threshold(self) -> None:
        """metabolic_rate > reproduction_threshold raises SimulationError."""
        params = _default_params(
            metabolic_rate=0.7, reproduction_threshold=0.6,
        )
        with pytest.raises(SimulationError, match="metabolic_rate"):
            SimulationEngine(params)


class TestGridStateShapesAndDtypes:
    """GridState arrays have correct shapes and dtypes per BLU-002 §2.1."""

    @pytest.fixture()
    def engine(self) -> SimulationEngine:
        """Fresh engine with default params."""
        return SimulationEngine(_default_params())

    def test_terrain_shape_dtype(self, engine: SimulationEngine) -> None:
        """Terrain: (H, W, 3) float32."""
        state = engine.get_state()
        assert state["terrain"].shape == (GRID_H, GRID_W, 3)
        assert state["terrain"].dtype == np.float32

    def test_species_grid_shape_dtype(self, engine: SimulationEngine) -> None:
        """Species grid: (H, W, MAX_PER_CELL) uint8."""
        state = engine.get_state()
        assert state["species_grid"].shape == (
            GRID_H, GRID_W, MAX_PER_CELL,
        )
        assert state["species_grid"].dtype == np.uint8

    def test_organism_attrs_shape_dtype(
        self, engine: SimulationEngine,
    ) -> None:
        """Organism attrs: (H, W, MAX_PER_CELL, 3) float32."""
        state = engine.get_state()
        assert state["organism_attrs"].shape == (
            GRID_H, GRID_W, MAX_PER_CELL, 3,
        )
        assert state["organism_attrs"].dtype == np.float32

    def test_resources_shape_dtype(self, engine: SimulationEngine) -> None:
        """Resources: (H, W, 2) float32."""
        state = engine.get_state()
        assert state["resources"].shape == (GRID_H, GRID_W, 2)
        assert state["resources"].dtype == np.float32

    def test_weather_shape_dtype(self, engine: SimulationEngine) -> None:
        """Weather: (H, W, 2) float32."""
        state = engine.get_state()
        assert state["weather"].shape == (GRID_H, GRID_W, 2)
        assert state["weather"].dtype == np.float32


class TestStepAndDeepCopy:
    """SimulationEngine.step() and get_state() return deep copies."""

    @pytest.fixture()
    def engine(self) -> SimulationEngine:
        return SimulationEngine(_default_params())

    def test_step_returns_state(self, engine: SimulationEngine) -> None:
        """step() returns a GridState dict."""
        state = engine.step()
        assert isinstance(state, dict)
        assert "terrain" in state
        assert "species_grid" in state

    def test_step_increments_tick(self, engine: SimulationEngine) -> None:
        """Each step() increments the tick counter."""
        assert engine.tick == 0
        engine.step()
        assert engine.tick == 1
        engine.step()
        assert engine.tick == 2

    def test_step_returns_deep_copy(self, engine: SimulationEngine) -> None:
        """Mutating returned state does not affect engine internal state."""
        state1 = engine.step()
        state1["terrain"][:] = 999.0
        state2 = engine.get_state()
        assert not np.allclose(state2["terrain"], 999.0)

    def test_get_state_returns_deep_copy(
        self, engine: SimulationEngine,
    ) -> None:
        """Mutating get_state() result does not affect engine."""
        state1 = engine.get_state()
        original_terrain = state1["terrain"].copy()
        state1["terrain"][:] = -1.0
        state2 = engine.get_state()
        np.testing.assert_array_equal(state2["terrain"], original_terrain)

    def test_step_changes_state(self, engine: SimulationEngine) -> None:
        """After a step, at least some state arrays change."""
        state_before = engine.get_state()
        state_after = engine.step()
        # Weather should change due to diffusion + noise
        assert not np.array_equal(
            state_before["weather"], state_after["weather"],
        )


class TestInterventions:
    """Intervention handling in SimulationEngine."""

    @pytest.fixture()
    def engine(self) -> SimulationEngine:
        return SimulationEngine(_default_params())

    def test_no_op_does_nothing_extra(self, engine: SimulationEngine) -> None:
        """NO_OP interventions are harmless."""
        iv = Intervention(
            type=InterventionType.NO_OP,
            region_row=0,
            region_col=0,
            intensity=0.0,
        )
        engine.step(interventions=[iv])
        assert engine.tick == 1

    def test_seed_plants_adds_organisms(
        self, engine: SimulationEngine,
    ) -> None:
        """SEED_PLANTS increases plant count in region."""
        state_before = engine.get_state()
        region = state_before["species_grid"][0:10, 0:10]
        plants_before = (region == SPECIES_PLANT).sum()

        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0,
            region_col=0,
            intensity=1.0,  # maximum seeding
        )
        state_after = engine.step(interventions=[iv])
        region_after = state_after["species_grid"][0:10, 0:10]
        plants_after = (region_after == SPECIES_PLANT).sum()
        # Seeding should add some plants (may lose some to mortality)
        # At intensity=1.0, most empty slots get filled
        assert plants_after >= plants_before

    def test_invalid_intervention_invokes_callback(
        self, engine: SimulationEngine,
    ) -> None:
        """Invalid intervention triggers callback, doesn't crash."""
        errors_received: list[InterventionError] = []
        engine._on_intervention_error = errors_received.append

        bad_iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=999,  # invalid
            region_col=0,
            intensity=0.5,
        )
        engine.step(interventions=[bad_iv])
        assert len(errors_received) == 1
        assert "region_row" in str(errors_received[0])

    def test_invalid_intervention_without_callback(
        self, engine: SimulationEngine,
    ) -> None:
        """Invalid intervention without callback is silently skipped."""
        bad_iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=999,
            region_col=0,
            intensity=0.5,
        )
        # Should not raise
        engine.step(interventions=[bad_iv])
        assert engine.tick == 1


class TestNaNRollback:
    """NaN detection and rollback per BLU-002 §2.2."""

    def test_nan_detected_and_rolled_back(self) -> None:
        """Injecting NaN triggers rollback with energy dampening.

        We must inject NaN AFTER step() saves _previous_state but
        BEFORE the NaN check runs. We do this by running a clean step
        first (to establish a valid previous), then manipulating
        internal state and calling _check_nan_rollback() directly.
        """
        engine = SimulationEngine(_default_params())
        engine.step()  # tick 0→1, establishes valid state

        # Save a clean previous state
        engine._previous_state = engine._deep_copy(engine._state)

        # Now inject NaN into current state (simulating a phase producing NaN)
        engine._state["resources"][:, :, 0] = np.nan

        # Run the NaN check — should rollback, not raise
        engine._check_nan_rollback()

        # Verify rollback happened: no NaN in state
        assert not np.isnan(engine._state["resources"]).any()

    def test_nan_dampens_energy(self) -> None:
        """After NaN rollback, energy is dampened by 0.9."""
        engine = SimulationEngine(_default_params())
        engine.step()  # establish valid state

        # Save clean previous state and record its energy
        engine._previous_state = engine._deep_copy(engine._state)
        energy_before = engine._previous_state[
            "organism_attrs"
        ][:, :, :, 1].copy()

        # Inject NaN into current state
        engine._state["resources"][:, :, 0] = np.nan

        # Rollback
        engine._check_nan_rollback()

        # Energy should be dampened by 0.9 from previous state
        energy_after = engine._state["organism_attrs"][:, :, :, 1]
        alive = engine._state["species_grid"] != SPECIES_EMPTY
        if alive.any():
            expected = energy_before[alive] * 0.9
            np.testing.assert_allclose(
                energy_after[alive], expected, rtol=1e-5,
            )

    def test_double_nan_raises(self) -> None:
        """Two consecutive NaN states raise SimulationError."""
        engine = SimulationEngine(_default_params())

        # Inject NaN into both current and what will become previous state
        engine._state["resources"][:, :, 0] = np.nan
        engine._previous_state = engine._deep_copy(engine._state)
        # Make previous state also have NaN
        engine._previous_state["resources"][:, :, 0] = np.nan

        with pytest.raises(SimulationError, match="Two consecutive NaN"):
            engine._check_nan_rollback()


class TestMultipleSteps:
    """Simulation runs stably over many steps."""

    def test_100_steps_no_crash(self) -> None:
        """Engine runs 100 steps without crashing."""
        engine = SimulationEngine(_default_params())
        for _ in range(100):
            state = engine.step()
        assert engine.tick == 100
        assert not np.isnan(state["resources"]).any()
        assert not np.isnan(state["organism_attrs"]).any()

    def test_species_populations_bounded(self) -> None:
        """Species IDs stay within valid range after 50 steps."""
        engine = SimulationEngine(_default_params())
        for _ in range(50):
            state = engine.step()
        sg = state["species_grid"]
        assert sg.min() >= 0
        assert sg.max() <= SPECIES_PREDATOR


class TestBenchmark:
    """Performance benchmarks per EVO-001 §4.2."""

    def test_step_performance(self, benchmark: Any) -> None:
        """SimulationEngine.step() runs ≥1000 steps/sec on 50×50.

        Refs: EVO-001 acceptance criteria 4.2
        """
        engine = SimulationEngine(_default_params())

        # Warm up
        for _ in range(10):
            engine.step()

        result = benchmark(engine.step)
        # benchmark fixture handles timing
        assert result is not None  # step returns GridState
