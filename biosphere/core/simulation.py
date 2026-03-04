"""Core simulation engine.

Vectorized NumPy simulation with 6-phase update cycle per BLU-001 §4.
No dependencies on any other biosphere.* module except biosphere.core.

Public API:
    SimulationParams — Protocol for configuration objects
    SimulationEngine — Stateful engine with step(), get_state(), tick
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import structlog

import numpy as np

from biosphere.core import phases
from biosphere.core.errors import InterventionError, SimulationError
from biosphere.core.state import (
    GRID_H,
    GRID_W,
    SPECIES_EMPTY,
    SPECIES_PLANT,
    GridState,
    Intervention,
    InterventionType,
)
from biosphere.infrastructure.logging import trace_execution

# ── Validation Constants ──────────────────────────────────────────────────────
MAX_AGE_LIMIT: int = 10_000
WEATHER_SIGMA_MAX: float = 10.0




@runtime_checkable
class SimulationParams(Protocol):
    """Structural type for simulation parameters.

    Any object with these attributes satisfies this protocol,
    including Pydantic models, dataclasses, or SimpleNamespace.

    Valid ranges (enforced by SimulationEngine.__init__):
        growth_rate:              (0.0, 1.0]
        reproduction_threshold:   (0.0, 1.0]
        max_age_prey:             [1, 10_000]
        max_age_predator:         [1, 10_000]
        metabolic_rate:           (0.0, 1.0]
        weather_sigma:            [0.0, 10.0]

    Invariant: metabolic_rate <= reproduction_threshold.
    """

    growth_rate: float
    reproduction_threshold: float
    max_age_prey: int
    max_age_predator: int
    metabolic_rate: float
    weather_sigma: float


class SimulationEngine:
    """Stateful simulation engine. Not thread-safe.

    Implements a 6-phase vectorized update cycle:
    1. Weather diffusion (Gaussian blur)
    2. Resource growth (logistic)
    3. Organism movement (random neighbor migration)
    4. Consumption (Holling Type II approximation)
    5. Reproduction (sigmoid probability)
    6. Mortality (age-based + starvation)

    Invalid interventions are handled via callback injection.
    Structured logging per GOV-006.
    """

    # Module-level logger (lazy-init so structlog can be configured first)
    _logger: structlog.stdlib.BoundLogger | None = None

    @classmethod
    def _get_logger(cls) -> structlog.stdlib.BoundLogger:
        if cls._logger is None:
            import structlog as _structlog
            cls._logger = _structlog.get_logger(component="simulation")
        return cls._logger

    def __init__(
        self,
        params: SimulationParams,
        on_intervention_error: Callable[[InterventionError], None] | None = None,
        seed: int = 42,
    ) -> None:
        """Initialize the simulation engine.

        Args:
            params: Configuration satisfying SimulationParams protocol.
            on_intervention_error: Optional callback for invalid interventions.
            seed: Random seed for deterministic behavior.

        Raises:
            SimulationError: If params fail validation.
        """
        self._validate_params(params)
        self._params = params
        self._on_intervention_error = on_intervention_error
        self._rng = np.random.default_rng(seed=seed)
        self._tick: int = 0
        self._state: GridState = self._initialize_state()
        self._previous_state: GridState | None = None
        self._get_logger().info(
            "engine.init",
            seed=seed,
            growth_rate=params.growth_rate,
            grid_size=f"{GRID_H}x{GRID_W}",
        )

    # ── Public API ────────────────────────────────────────────────────────────

    @trace_execution
    def step(
        self, interventions: list[Intervention] | None = None,
    ) -> GridState:
        """Execute one tick of the simulation.

        Args:
            interventions: Optional domain-level interventions to apply
                before the tick. Invalid ones invoke the callback and
                are skipped (treated as NO_OP).

        Returns:
            Deep copy of the updated GridState.

        Raises:
            SimulationError: If NaN rollback fails (two consecutive NaN).
        """
        # Save previous state for NaN rollback
        self._previous_state = self._deep_copy(self._state)

        # Apply interventions
        if interventions:
            self._apply_interventions(interventions)

        # 6-phase update cycle
        self._phase_weather_diffusion()
        self._phase_resource_growth()
        self._phase_movement()
        self._phase_consumption()
        self._phase_reproduction()
        self._phase_mortality()

        # NaN check and rollback
        self._check_nan_rollback()

        self._tick += 1
        self._get_logger().debug(
            "engine.step.exit",
            tick=self._tick,
            n_interventions=len(interventions) if interventions else 0,
        )
        return self._deep_copy(self._state)

    def get_state(self) -> GridState:
        """Return a deep copy of the current state.

        The caller owns the returned arrays and may mutate them.
        """
        return self._deep_copy(self._state)

    @property
    def tick(self) -> int:
        """Current simulation tick count."""
        return self._tick

    # ── Parameter Validation ──────────────────────────────────────────────────

    @staticmethod
    def _validate_params(params: SimulationParams) -> None:
        """Validate all parameter ranges. Defense in depth.

        Raises:
            SimulationError: If any parameter is out of valid range.
        """
        if not (0.0 < params.growth_rate <= 1.0):
            raise SimulationError(
                f"growth_rate must be in (0.0, 1.0], got {params.growth_rate}",
            )
        if not (0.0 < params.reproduction_threshold <= 1.0):
            raise SimulationError(
                f"reproduction_threshold must be in (0.0, 1.0], "
                f"got {params.reproduction_threshold}",
            )
        if not (1 <= params.max_age_prey <= MAX_AGE_LIMIT):
            raise SimulationError(
                f"max_age_prey must be in [1, 10000], "
                f"got {params.max_age_prey}",
            )
        if not (1 <= params.max_age_predator <= MAX_AGE_LIMIT):
            raise SimulationError(
                f"max_age_predator must be in [1, 10000], "
                f"got {params.max_age_predator}",
            )
        if not (0.0 < params.metabolic_rate <= 1.0):
            raise SimulationError(
                f"metabolic_rate must be in (0.0, 1.0], "
                f"got {params.metabolic_rate}",
            )
        if not (0.0 <= params.weather_sigma <= WEATHER_SIGMA_MAX):
            raise SimulationError(
                f"weather_sigma must be in [0.0, 10.0], "
                f"got {params.weather_sigma}",
            )
        if params.metabolic_rate > params.reproduction_threshold:
            raise SimulationError(
                f"metabolic_rate ({params.metabolic_rate}) must be <= "
                f"reproduction_threshold ({params.reproduction_threshold})",
            )

    # ── State Initialization ──────────────────────────────────────────────────

    def _initialize_state(self) -> GridState:
        """Generate the initial world state.

        Delegates to phases.init_terrain/init_organisms/init_resources.
        """
        terrain = phases.init_terrain(self._rng)
        species_grid, organism_attrs = phases.init_organisms(self._rng)
        resources = phases.init_resources(terrain, self._rng)

        # Weather: moderate starting conditions
        weather = np.zeros((GRID_H, GRID_W, 2), dtype=np.float32)
        weather[:, :, 0] = 0.5  # precipitation
        weather[:, :, 1] = 0.7  # sunlight

        return GridState(
            terrain=terrain,
            species_grid=species_grid,
            organism_attrs=organism_attrs,
            resources=resources,
            weather=weather,
        )

    # ── Intervention Application ──────────────────────────────────────────────

    def _apply_interventions(
        self, interventions: list[Intervention],
    ) -> None:
        """Apply a list of interventions before the tick.

        Invalid interventions invoke the callback and are skipped.
        """
        for intervention in interventions:
            if intervention.type == InterventionType.NO_OP:
                continue
            try:
                intervention.validate()
            except InterventionError as e:
                if self._on_intervention_error:
                    self._on_intervention_error(e)
                continue

            r0 = intervention.region_row
            c0 = intervention.region_col
            region = slice(r0, r0 + 10), slice(c0, c0 + 10)

            if intervention.type == InterventionType.SEED_PLANTS:
                self._intervene_seed_plants(region, intervention.intensity)
            elif intervention.type == InterventionType.ADJUST_PRECIPITATION:
                self._intervene_adjust_precipitation(
                    region, intervention.intensity,
                )
            elif intervention.type == InterventionType.CULL_SPECIES:
                self._intervene_cull_species(
                    region, intervention.intensity, intervention.target_species,
                )

    def _intervene_seed_plants(
        self,
        region: tuple[slice, slice],
        intensity: float,
    ) -> None:
        """Seed plants in empty slots within the region."""
        sg = self._state["species_grid"][region]
        oa = self._state["organism_attrs"][region]
        empty = sg == SPECIES_EMPTY
        # Probabilistically fill empty slots
        fill_mask = empty & (
            self._rng.random(sg.shape).astype(np.float32) < intensity
        )
        sg[fill_mask] = SPECIES_PLANT
        oa[fill_mask, 0] = 0.8  # health
        oa[fill_mask, 1] = 0.5  # energy
        oa[fill_mask, 2] = 0.0  # age

    def _intervene_adjust_precipitation(
        self,
        region: tuple[slice, slice],
        intensity: float,
    ) -> None:
        """Adjust precipitation in the region. Intensity maps to [-0.5, +0.5]."""
        delta = (intensity - 0.5) * 1.0  # maps [0,1] → [-0.5, +0.5]
        self._state["weather"][region][:, :, 0] = np.clip(
            self._state["weather"][region][:, :, 0] + delta, 0.0, 1.0,
        )

    def _intervene_cull_species(
        self,
        region: tuple[slice, slice],
        intensity: float,
        target_species: int,
    ) -> None:
        """Remove a fraction of target species from the region."""
        sg = self._state["species_grid"][region]
        oa = self._state["organism_attrs"][region]
        target_mask = sg == target_species
        # Probabilistically remove based on intensity
        cull_mask = target_mask & (
            self._rng.random(sg.shape).astype(np.float32) < intensity
        )
        sg[cull_mask] = SPECIES_EMPTY
        oa[cull_mask] = 0.0

    # ── Phase Delegates (see biosphere/core/phases.py) ──────────────────────

    def _phase_weather_diffusion(self) -> None:
        """Delegate to phases.phase_weather_diffusion."""
        phases.phase_weather_diffusion(self._state, self._params, self._rng)

    def _phase_resource_growth(self) -> None:
        """Delegate to phases.phase_resource_growth."""
        phases.phase_resource_growth(self._state, self._params)

    def _phase_movement(self) -> None:
        """Delegate to phases.phase_movement."""
        phases.phase_movement(self._state, self._rng)

    def _phase_consumption(self) -> None:
        """Delegate to phases.phase_consumption."""
        phases.phase_consumption(self._state)

    def _phase_reproduction(self) -> None:
        """Delegate to phases.phase_reproduction."""
        phases.phase_reproduction(self._state, self._params, self._rng)

    def _phase_mortality(self) -> None:
        """Delegate to phases.phase_mortality."""
        phases.phase_mortality(self._state, self._params)

    # ── NaN Protection ────────────────────────────────────────────────────────

    def _check_nan_rollback(self) -> None:
        """Check for NaN in float32 arrays and rollback if found.

        On NaN detection: restore previous state, dampen energy by 0.9.
        Two consecutive NaN states raise SimulationError.
        """
        has_nan = (
            np.isnan(self._state["terrain"]).any()
            or np.isnan(self._state["organism_attrs"]).any()
            or np.isnan(self._state["resources"]).any()
            or np.isnan(self._state["weather"]).any()
        )

        if not has_nan:
            return

        if self._previous_state is None:
            raise SimulationError(
                "NaN detected in initial state — cannot rollback",
            )

        # Check if previous state also had NaN
        prev_nan = (
            np.isnan(self._previous_state["terrain"]).any()
            or np.isnan(self._previous_state["organism_attrs"]).any()
            or np.isnan(self._previous_state["resources"]).any()
            or np.isnan(self._previous_state["weather"]).any()
        )
        if prev_nan:
            raise SimulationError(
                "Two consecutive NaN states detected — unrecoverable",
            )

        # Rollback to previous state
        self._state = self._deep_copy(self._previous_state)

        # Dampen energy by 0.9
        self._state["organism_attrs"][:, :, :, 1] *= 0.9

        self._get_logger().warning(
            "engine.nan_rollback",
            tick=self._tick,
            message="NaN detected — rolled back to previous state, energy dampened",
        )

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _deep_copy(state: GridState) -> GridState:
        """Create a deep copy of GridState (all arrays copied)."""
        return GridState(
            terrain=state["terrain"].copy(),
            species_grid=state["species_grid"].copy(),
            organism_attrs=state["organism_attrs"].copy(),
            resources=state["resources"].copy(),
            weather=state["weather"].copy(),
        )
