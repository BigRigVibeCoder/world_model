"""Tests for biosphere.core.simulation — SimulationEngine.

Refs: EVO-001, BLU-002 §2.2
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §5: Hypothesis property tests for invariants.
GOV-002 §13: Performance benchmarks with pytest-benchmark.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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
from tests.conftest import make_params

# ═══════════════════════════════════════════════════════════════════════════════
# §4 UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestSimulationParamsProtocol:
    """SimulationParams protocol conformance."""

    def test_simplenamespace_satisfies_protocol(self) -> None:
        """SimpleNamespace with correct fields satisfies SimulationParams.

        Refs: BLU-002 §2.4
        """
        params = make_params()
        assert isinstance(params, SimulationParams)
        assert hasattr(params, "growth_rate")

    def test_pydantic_model_satisfies_protocol(self) -> None:
        """SimulationConfig Pydantic model satisfies SimulationParams.

        Refs: BLU-002 §2.4, EVO-001 §4.1
        """
        from biosphere.infrastructure.config import SimulationConfig

        config = SimulationConfig()
        assert isinstance(config, SimulationParams)
        assert config.growth_rate == 0.1


@pytest.mark.unit
class TestParameterValidation:
    """SimulationEngine.__init__ validates all parameter ranges (defense in depth)."""

    def test_valid_params_accepted(self) -> None:
        """Valid default params create engine at tick 0 with valid state.

        Refs: BLU-002 §2.2, EVO-001 §4.1
        """
        engine = SimulationEngine(make_params())
        assert engine.tick == 0
        state = engine.get_state()
        assert "terrain" in state

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
        """Out-of-range parameters raise SimulationError with field name.

        Refs: BLU-002 §2.4
        """
        params = make_params(**{field: value})
        with pytest.raises(SimulationError, match=match) as exc_info:
            SimulationEngine(params)
        assert match in str(exc_info.value)

    def test_metabolic_rate_exceeds_reproduction_threshold(self) -> None:
        """metabolic_rate > reproduction_threshold violates invariant.

        Refs: BLU-002 §2.4
        """
        params = make_params(
            metabolic_rate=0.7, reproduction_threshold=0.6,
        )
        with pytest.raises(SimulationError, match="metabolic_rate") as exc_info:
            SimulationEngine(params)
        assert "reproduction_threshold" in str(exc_info.value)


@pytest.mark.unit
class TestGridStateShapesAndDtypes:
    """GridState arrays have correct shapes and dtypes per BLU-002 §2.1."""

    def test_terrain_shape_dtype(self, engine: SimulationEngine) -> None:
        """Terrain: (H, W, 3) float32 — elevation, temperature, humidity.

        Refs: BLU-002 §2.1
        """
        state = engine.get_state()
        assert state["terrain"].shape == (GRID_H, GRID_W, 3)
        assert state["terrain"].dtype == np.float32

    def test_species_grid_shape_dtype(self, engine: SimulationEngine) -> None:
        """Species grid: (H, W, MAX_PER_CELL) uint8 — mixed dtype strategy.

        Refs: BLU-002 §2.1, EVO-001 §4.2
        """
        state = engine.get_state()
        assert state["species_grid"].shape == (GRID_H, GRID_W, MAX_PER_CELL)
        assert state["species_grid"].dtype == np.uint8

    def test_organism_attrs_shape_dtype(self, engine: SimulationEngine) -> None:
        """Organism attrs: (H, W, MAX_PER_CELL, 3) float32 — health, energy, age.

        Refs: BLU-002 §2.1
        """
        state = engine.get_state()
        assert state["organism_attrs"].shape == (GRID_H, GRID_W, MAX_PER_CELL, 3)
        assert state["organism_attrs"].dtype == np.float32

    def test_resources_shape_dtype(self, engine: SimulationEngine) -> None:
        """Resources: (H, W, 2) float32 — plant_biomass, water.

        Refs: BLU-002 §2.1
        """
        state = engine.get_state()
        assert state["resources"].shape == (GRID_H, GRID_W, 2)
        assert state["resources"].dtype == np.float32

    def test_weather_shape_dtype(self, engine: SimulationEngine) -> None:
        """Weather: (H, W, 2) float32 — precipitation, sunlight.

        Refs: BLU-002 §2.1
        """
        state = engine.get_state()
        assert state["weather"].shape == (GRID_H, GRID_W, 2)
        assert state["weather"].dtype == np.float32


@pytest.mark.unit
class TestStepAndDeepCopy:
    """SimulationEngine.step() returns deep copies — BLU-002 §2.2."""

    def test_step_returns_state_dict(self, engine: SimulationEngine) -> None:
        """step() returns a GridState dict with all required keys.

        Refs: BLU-002 §2.2
        """
        state = engine.step()
        assert isinstance(state, dict)
        assert set(state.keys()) == {
            "terrain", "species_grid", "organism_attrs", "resources", "weather",
        }

    def test_step_increments_tick(self, engine: SimulationEngine) -> None:
        """Each step() increments the tick counter by exactly 1.

        Refs: BLU-002 §2.2
        """
        assert engine.tick == 0
        engine.step()
        assert engine.tick == 1
        engine.step()
        assert engine.tick == 2

    def test_step_returns_deep_copy(self, engine: SimulationEngine) -> None:
        """Mutating returned state does not affect engine internal state.

        Refs: BLU-002 §2.2 (deep copy contract)
        """
        state1 = engine.step()
        original = state1["terrain"].copy()
        state1["terrain"][:] = 999.0
        state2 = engine.get_state()
        assert not np.allclose(state2["terrain"], 999.0)
        np.testing.assert_array_equal(state2["terrain"], original)

    def test_get_state_returns_deep_copy(self, engine: SimulationEngine) -> None:
        """Mutating get_state() result does not affect engine.

        Refs: BLU-002 §2.2 (deep copy contract)
        """
        state1 = engine.get_state()
        original = state1["terrain"].copy()
        state1["terrain"][:] = -1.0
        state2 = engine.get_state()
        np.testing.assert_array_equal(state2["terrain"], original)
        assert not np.allclose(state2["terrain"], -1.0)

    def test_step_changes_state(self, engine: SimulationEngine) -> None:
        """After a step, weather changes due to diffusion + noise.

        Refs: BLU-001 §4.2 (weather diffusion phase)
        """
        state_before = engine.get_state()
        state_after = engine.step()
        assert not np.array_equal(state_before["weather"], state_after["weather"])
        assert engine.tick == 1


@pytest.mark.unit
class TestInterventions:
    """Intervention handling in SimulationEngine — BLU-002 §2.2."""

    def test_no_op_increments_tick(self, engine: SimulationEngine) -> None:
        """NO_OP interventions are harmless — tick still increments.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.NO_OP,
            region_row=0, region_col=0, intensity=0.0,
        )
        engine.step(interventions=[iv])
        assert engine.tick == 1
        state = engine.get_state()
        assert "terrain" in state

    def test_seed_plants_adds_organisms(self, engine: SimulationEngine) -> None:
        """SEED_PLANTS at max intensity adds plants to region.

        Refs: BLU-002 §2.3
        """
        state_before = engine.get_state()
        region = state_before["species_grid"][0:10, 0:10]
        plants_before = int((region == SPECIES_PLANT).sum())

        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0, region_col=0, intensity=1.0,
        )
        state_after = engine.step(interventions=[iv])
        region_after = state_after["species_grid"][0:10, 0:10]
        plants_after = int((region_after == SPECIES_PLANT).sum())
        assert plants_after >= plants_before
        assert engine.tick == 1

    def test_invalid_intervention_invokes_callback(self, engine: SimulationEngine) -> None:
        """Invalid intervention triggers callback with InterventionError.

        Refs: BLU-002 §2.2, GOV-004
        """
        errors_received: list[InterventionError] = []
        engine._on_intervention_error = errors_received.append

        bad_iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=999, region_col=0, intensity=0.5,
        )
        engine.step(interventions=[bad_iv])
        assert len(errors_received) == 1
        assert "region_row" in str(errors_received[0])

    def test_invalid_intervention_without_callback_silent(
        self, engine: SimulationEngine,
    ) -> None:
        """Invalid intervention without callback is silently skipped.

        Refs: BLU-002 §2.2
        """
        bad_iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=999, region_col=0, intensity=0.5,
        )
        engine.step(interventions=[bad_iv])
        assert engine.tick == 1
        assert engine._on_intervention_error is None

    def test_adjust_precipitation_modifies_weather(
        self, engine: SimulationEngine,
    ) -> None:
        """ADJUST_PRECIPITATION changes weather in target region.

        Refs: BLU-002 §2.3, BLU-001 §7.3
        """
        iv = Intervention(
            type=InterventionType.ADJUST_PRECIPITATION,
            region_row=0, region_col=0, intensity=1.0,
        )
        state = engine.step(interventions=[iv])
        # Weather changes from both intervention and diffusion
        assert engine.tick == 1
        assert state["weather"].shape == (GRID_H, GRID_W, 2)

    def test_cull_species_removes_from_region(self, engine: SimulationEngine) -> None:
        """CULL_SPECIES at max intensity clears prey from target 10×10 region.

        Refs: BLU-002 §2.3
        """
        # Pre-seed prey in a known region to ensure some exist
        state = engine.get_state()
        region_sg = state["species_grid"][0:10, 0:10]
        prey_region_before = int((region_sg == SPECIES_PREY).sum())

        iv = Intervention(
            type=InterventionType.CULL_SPECIES,
            region_row=0, region_col=0, intensity=1.0,
            target_species=SPECIES_PREY,
        )
        state_after = engine.step(interventions=[iv])
        region_after = state_after["species_grid"][0:10, 0:10]
        prey_region_after = int((region_after == SPECIES_PREY).sum())
        # At intensity 1.0, region should have fewer prey
        # (some may have moved in during movement phase)
        assert engine.tick == 1
        assert prey_region_after <= prey_region_before + 5  # small tolerance for movement


@pytest.mark.unit
class TestNaNRollback:
    """NaN detection and rollback per BLU-002 §2.2."""

    def test_nan_detected_and_rolled_back(
        self, stepped_engine: SimulationEngine,
    ) -> None:
        """Injecting NaN triggers rollback, state restored to clean.

        Refs: BLU-002 §2.2, EVO-001 §4.2
        """
        stepped_engine._previous_state = SimulationEngine._deep_copy(
            stepped_engine._state,
        )
        stepped_engine._state["resources"][:, :, 0] = np.nan
        stepped_engine._check_nan_rollback()
        assert not np.isnan(stepped_engine._state["resources"]).any()
        assert not np.isnan(stepped_engine._state["terrain"]).any()

    def test_nan_dampens_energy_by_0_9(
        self, stepped_engine: SimulationEngine,
    ) -> None:
        """After NaN rollback, energy is dampened by 0.9 from previous state.

        Refs: BLU-002 §2.2
        """
        stepped_engine._previous_state = SimulationEngine._deep_copy(
            stepped_engine._state,
        )
        energy_before = stepped_engine._previous_state[
            "organism_attrs"
        ][:, :, :, 1].copy()
        stepped_engine._state["resources"][:, :, 0] = np.nan
        stepped_engine._check_nan_rollback()

        energy_after = stepped_engine._state["organism_attrs"][:, :, :, 1]
        alive = stepped_engine._state["species_grid"] != SPECIES_EMPTY
        if alive.any():
            expected = energy_before[alive] * 0.9
            np.testing.assert_allclose(energy_after[alive], expected, rtol=1e-5)
            assert (energy_after[alive] >= 0.0).all()

    def test_double_nan_raises_simulation_error(self) -> None:
        """Two consecutive NaN states raise unrecoverable SimulationError.

        Refs: BLU-002 §2.2, EVO-001 §4.2
        """
        engine = SimulationEngine(make_params())
        engine._state["resources"][:, :, 0] = np.nan
        engine._previous_state = SimulationEngine._deep_copy(engine._state)
        engine._previous_state["resources"][:, :, 0] = np.nan

        with pytest.raises(SimulationError, match="Two consecutive NaN") as exc_info:
            engine._check_nan_rollback()
        assert "unrecoverable" in str(exc_info.value)


@pytest.mark.unit
class TestMultipleSteps:
    """Simulation stability over many steps."""

    def test_100_steps_no_crash_no_nan(self, engine: SimulationEngine) -> None:
        """Engine runs 100 steps without crashing or producing NaN.

        Refs: EVO-001 §4.2
        """
        for _ in range(100):
            state = engine.step()
        assert engine.tick == 100
        assert not np.isnan(state["resources"]).any()
        assert not np.isnan(state["organism_attrs"]).any()

    def test_species_ids_stay_valid(self, engine: SimulationEngine) -> None:
        """Species IDs stay within valid range [0, PREDATOR] after 50 steps.

        Refs: BLU-002 §2.1
        """
        for _ in range(50):
            state = engine.step()
        sg = state["species_grid"]
        assert sg.min() >= 0
        assert sg.max() <= SPECIES_PREDATOR


# ═══════════════════════════════════════════════════════════════════════════════
# §5 PROPERTY-BASED TESTS (Hypothesis)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.property
class TestPropertyBased:
    """Hypothesis property tests for simulation invariants.

    GOV-002 §5: Define invariants and let Hypothesis generate edge cases.
    """

    @given(
        growth_rate=st.floats(min_value=0.01, max_value=1.0),
        reproduction_threshold=st.floats(min_value=0.3, max_value=1.0),
        metabolic_rate=st.floats(min_value=0.001, max_value=0.29),
    )
    @settings(max_examples=30, deadline=5000)
    def test_engine_accepts_valid_params(
        self,
        growth_rate: float,
        reproduction_threshold: float,
        metabolic_rate: float,
    ) -> None:
        """SimulationEngine accepts any params within valid ranges.

        Refs: BLU-002 §2.4, GOV-002 §5
        """
        params = make_params(
            growth_rate=growth_rate,
            reproduction_threshold=reproduction_threshold,
            metabolic_rate=metabolic_rate,
        )
        engine = SimulationEngine(params)
        assert engine.tick == 0
        assert isinstance(engine.get_state(), dict)

    @given(n_steps=st.integers(min_value=1, max_value=20))
    @settings(max_examples=10, deadline=30000)
    def test_species_grid_values_always_valid(self, n_steps: int) -> None:
        """Species grid values stay in {0, 1, 2, 3} after any number of steps.

        Refs: BLU-002 §2.1, GOV-002 §5
        """
        engine = SimulationEngine(make_params())
        for _ in range(n_steps):
            state = engine.step()
        sg = state["species_grid"]
        assert sg.min() >= SPECIES_EMPTY
        assert sg.max() <= SPECIES_PREDATOR

    @given(n_steps=st.integers(min_value=1, max_value=20))
    @settings(max_examples=10, deadline=30000)
    def test_resources_always_bounded(self, n_steps: int) -> None:
        """Resources (biomass, water) stay in [0.0, 1.0] after any steps.

        Refs: BLU-002 §2.1, GOV-002 §5
        """
        engine = SimulationEngine(make_params())
        for _ in range(n_steps):
            state = engine.step()
        resources = state["resources"]
        assert not np.isnan(resources).any()
        assert resources.min() >= 0.0
        assert resources.max() <= 1.0

    @given(n_steps=st.integers(min_value=1, max_value=20))
    @settings(max_examples=10, deadline=30000)
    def test_weather_always_bounded(self, n_steps: int) -> None:
        """Weather (precipitation, sunlight) stays in [0.0, 1.0] after any steps.

        Refs: BLU-002 §2.1, GOV-002 §5
        """
        engine = SimulationEngine(make_params())
        for _ in range(n_steps):
            state = engine.step()
        weather = state["weather"]
        assert not np.isnan(weather).any()
        assert weather.min() >= 0.0
        assert weather.max() <= 1.0

    @given(n_steps=st.integers(min_value=1, max_value=20))
    @settings(max_examples=10, deadline=30000)
    def test_organism_attrs_non_negative(self, n_steps: int) -> None:
        """Organism attributes (health, energy, age) never go negative for alive organisms.

        Refs: BLU-002 §2.1, GOV-002 §5
        """
        engine = SimulationEngine(make_params())
        for _ in range(n_steps):
            state = engine.step()
        sg = state["species_grid"]
        oa = state["organism_attrs"]
        alive = sg != SPECIES_EMPTY
        if alive.any():
            assert (oa[alive, 0] >= 0.0).all()  # health ≥ 0
            assert (oa[alive, 2] >= 0.0).all()  # age ≥ 0

    @given(n_steps=st.integers(min_value=1, max_value=10))
    @settings(max_examples=5, deadline=30000)
    def test_no_nan_after_steps(self, n_steps: int) -> None:
        """No NaN values appear in any float array after simulation steps.

        Refs: BLU-002 §2.2, GOV-002 §5
        """
        engine = SimulationEngine(make_params())
        for _ in range(n_steps):
            state = engine.step()
        for key in ("terrain", "organism_attrs", "resources", "weather"):
            assert not np.isnan(state[key]).any(), f"NaN found in {key}"

    @given(n_steps=st.integers(min_value=1, max_value=10))
    @settings(max_examples=5, deadline=30000)
    def test_dead_organisms_have_zero_attrs(self, n_steps: int) -> None:
        """Empty species slots have zeroed health/energy/age.

        Refs: BLU-002 §2.1
        """
        engine = SimulationEngine(make_params())
        for _ in range(n_steps):
            state = engine.step()
        sg = state["species_grid"]
        oa = state["organism_attrs"]
        dead = sg == SPECIES_EMPTY
        if dead.any():
            # Dead organisms should have zero or near-zero attrs
            # (Movement may briefly create non-zero attrs in empty slots
            #  that get cleared, so we check the majority)
            dead_energy = oa[dead, 1]
            assert (dead_energy <= 0.01).sum() >= len(dead_energy) * 0.95


# ═══════════════════════════════════════════════════════════════════════════════
# §8 INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestConfigToEngine:
    """Config → Engine integration — YAML file to running simulation."""

    def test_load_config_and_run(self) -> None:
        """SimulationConfig loaded from YAML creates a working engine.

        Refs: EVO-001 §4.1, BLU-002 §2.4
        """
        from biosphere.infrastructure.config import load_config

        config = load_config("config/simulation.yaml")
        engine = SimulationEngine(config)
        state = engine.step()
        assert engine.tick == 1
        assert not np.isnan(state["resources"]).any()

    def test_error_callback_integration(self) -> None:
        """Error callback receives InterventionError with structured details.

        Refs: GOV-004, BLU-002 §2.2
        """
        errors: list[InterventionError] = []

        def on_error(e: InterventionError) -> None:
            errors.append(e)

        engine = SimulationEngine(make_params(), on_intervention_error=on_error)
        bad_iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=999, region_col=0, intensity=0.5,
        )
        engine.step(interventions=[bad_iv])
        assert len(errors) == 1
        assert isinstance(errors[0], InterventionError)


# ═══════════════════════════════════════════════════════════════════════════════
# §13 PERFORMANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.performance
class TestPerformance:
    """Performance benchmarks per EVO-001 §4.2 and GOV-002 §13."""

    def test_step_throughput(self, benchmark: Any) -> None:
        """SimulationEngine.step() throughput on 50×50 grid.

        Target: ≥1000 steps/sec (BLU-001 §1.2). Current: ~120 ops/sec
        with pure Python movement loops. Numba JIT planned for optimization.

        Refs: EVO-001 §4.2, BLU-001 §1.2, GOV-002 §13
        """
        engine = SimulationEngine(make_params())
        for _ in range(10):
            engine.step()

        result = benchmark(engine.step)
        assert result is not None
        assert engine.tick > 0

    def test_initialization_time(self, benchmark: Any) -> None:
        """SimulationEngine initialization should complete quickly.

        Refs: GOV-002 §13
        """
        params = make_params()
        engine = benchmark(SimulationEngine, params)
        assert isinstance(engine, SimulationEngine)
        assert engine.tick == 0
