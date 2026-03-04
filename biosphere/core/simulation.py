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
from scipy.ndimage import gaussian_filter  # type: ignore[import-untyped]

from biosphere.core.errors import InterventionError, SimulationError
from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
    GridState,
    Intervention,
    InterventionType,
)

# ── Validation Constants ──────────────────────────────────────────────────────
MAX_AGE_LIMIT: int = 10_000
WEATHER_SIGMA_MAX: float = 10.0

# ── Initialization Constants ─────────────────────────────────────────────────
INIT_PLANT_DENSITY: float = 0.3
INIT_PREY_DENSITY: float = 0.1
INIT_PREDATOR_DENSITY: float = 0.03
MOVEMENT_PROBABILITY: float = 0.2


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

        Creates a randomized but ecologically plausible starting condition:
        - Terrain: smooth random elevation, temperature gradient, humidity
        - Species: scattered plants, few prey, fewer predators
        - Resources: correlated with terrain
        - Weather: uniform moderate conditions
        """
        rng = self._rng

        # Terrain: smooth random fields
        terrain = np.zeros((GRID_H, GRID_W, 3), dtype=np.float32)
        terrain[:, :, 0] = gaussian_filter(
            rng.random((GRID_H, GRID_W), dtype=np.float32), sigma=5.0,
        )  # elevation
        terrain[:, :, 1] = np.linspace(
            20.0, 35.0, GRID_H, dtype=np.float32,
        )[:, np.newaxis] + rng.normal(
            0, 2, (GRID_H, GRID_W),
        ).astype(np.float32)  # temperature
        terrain[:, :, 2] = np.clip(
            gaussian_filter(
                rng.random((GRID_H, GRID_W), dtype=np.float32), sigma=3.0,
            ),
            0.0,
            1.0,
        )  # humidity

        # Species grid: sparse initial population
        species_grid = np.zeros(
            (GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8,
        )
        # Plants: ~30% of cells get 1-3 plants
        plant_mask = rng.random((GRID_H, GRID_W)) < INIT_PLANT_DENSITY
        for row, col in zip(*np.where(plant_mask), strict=True):
            n_plants = rng.integers(1, 4)
            species_grid[row, col, :n_plants] = SPECIES_PLANT

        # Prey: ~10% of cells get 1 prey
        prey_mask = rng.random((GRID_H, GRID_W)) < INIT_PREY_DENSITY
        for row, col in zip(*np.where(prey_mask), strict=True):
            empty_slots = np.where(
                species_grid[row, col] == SPECIES_EMPTY,
            )[0]
            if len(empty_slots) > 0:
                species_grid[row, col, empty_slots[0]] = SPECIES_PREY

        # Predators: ~3% of cells get 1 predator
        pred_mask = rng.random((GRID_H, GRID_W)) < INIT_PREDATOR_DENSITY
        for row, col in zip(*np.where(pred_mask), strict=True):
            empty_slots = np.where(
                species_grid[row, col] == SPECIES_EMPTY,
            )[0]
            if len(empty_slots) > 0:
                species_grid[row, col, empty_slots[0]] = SPECIES_PREDATOR

        # Organism attributes: health, energy, age
        organism_attrs = np.zeros(
            (GRID_H, GRID_W, MAX_PER_CELL, 3), dtype=np.float32,
        )
        alive_mask = species_grid > SPECIES_EMPTY
        organism_attrs[alive_mask, 0] = rng.uniform(
            0.5, 1.0, size=int(alive_mask.sum()),
        ).astype(np.float32)  # health
        organism_attrs[alive_mask, 1] = rng.uniform(
            0.3, 0.8, size=int(alive_mask.sum()),
        ).astype(np.float32)  # energy
        organism_attrs[alive_mask, 2] = rng.uniform(
            0.0, 50.0, size=int(alive_mask.sum()),
        ).astype(np.float32)  # age

        # Resources: correlated with terrain humidity
        resources = np.zeros((GRID_H, GRID_W, 2), dtype=np.float32)
        resources[:, :, 0] = np.clip(
            terrain[:, :, 2] * 0.8
            + rng.normal(0, 0.1, (GRID_H, GRID_W)).astype(np.float32),
            0.0,
            1.0,
        )  # plant_biomass
        resources[:, :, 1] = np.clip(
            terrain[:, :, 2] * 0.9
            + rng.normal(0, 0.05, (GRID_H, GRID_W)).astype(np.float32),
            0.0,
            1.0,
        )  # water

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

    # ── Phase 1: Weather Diffusion ────────────────────────────────────────────

    def _phase_weather_diffusion(self) -> None:
        """Spatially diffuse weather patterns using Gaussian blur."""
        sigma = self._params.weather_sigma
        if sigma > 0.0:
            weather = self._state["weather"]
            # Add small random perturbation before diffusion
            rng = self._rng
            noise = rng.normal(0, 0.02, weather.shape).astype(np.float32)
            weather += noise
            for ch in range(weather.shape[2]):
                weather[:, :, ch] = gaussian_filter(
                    weather[:, :, ch], sigma=sigma,
                ).astype(np.float32)
            np.clip(weather, 0.0, 1.0, out=weather)

    # ── Phase 2: Resource Growth ──────────────────────────────────────────────

    def _phase_resource_growth(self) -> None:
        """Logistic resource growth: dP/dt = rP(1 - P/K).

        Plant biomass grows based on sunlight and precipitation.
        Water replenishes based on precipitation.
        """
        r = self._params.growth_rate
        resources = self._state["resources"]
        weather = self._state["weather"]

        # Plant biomass: logistic growth modulated by sunlight
        sunlight = weather[:, :, 1]
        biomass = resources[:, :, 0]
        growth = r * biomass * (1.0 - biomass) * sunlight
        resources[:, :, 0] = np.clip(biomass + growth, 0.0, 1.0)

        # Water: replenishment from precipitation
        precip = weather[:, :, 0]
        water = resources[:, :, 1]
        water_delta = 0.1 * precip - 0.05  # net change
        resources[:, :, 1] = np.clip(water + water_delta, 0.0, 1.0)

    # ── Phase 3: Movement ─────────────────────────────────────────────────────

    def _phase_movement(self) -> None:
        """Random neighbor migration for mobile organisms.

        Prey and predators migrate to adjacent cells probabilistically.
        Plants do not move. Uses vectorized approach: randomly shift
        a fraction of organisms to adjacent cells with available slots.
        """
        sg = self._state["species_grid"]
        oa = self._state["organism_attrs"]

        for species_id in (SPECIES_PREY, SPECIES_PREDATOR):
            mask = sg == species_id
            if not mask.any():
                continue

            # ~20% of organisms attempt to move each tick
            movers = mask & (
                self._rng.random(mask.shape).astype(np.float32) < MOVEMENT_PROBABILITY
            )
            if not movers.any():
                continue

            # Collapse to cell level: pick one random mover per cell
            mover_cells = np.any(movers, axis=2)
            if not mover_cells.any():
                continue

            # For each cell with a mover, compute target cell
            cell_rows, cell_cols = np.where(mover_cells)
            n_movers = len(cell_rows)

            # Random direction: 0=N, 1=S, 2=W, 3=E
            dirs = self._rng.integers(0, 4, size=n_movers)
            dr = np.array([-1, 1, 0, 0])[dirs]
            dc = np.array([0, 0, -1, 1])[dirs]
            target_rows = cell_rows + dr
            target_cols = cell_cols + dc

            # Boundary mask
            valid = (
                (target_rows >= 0)
                & (target_rows < GRID_H)
                & (target_cols >= 0)
                & (target_cols < GRID_W)
            )

            # Process only valid moves
            for idx in np.where(valid)[0]:
                sr, sc = int(cell_rows[idx]), int(cell_cols[idx])
                tr, tc = int(target_rows[idx]), int(target_cols[idx])

                # Find first mover slot in source cell
                src_slots = np.where(movers[sr, sc])[0]
                if len(src_slots) == 0:
                    continue
                ss = int(src_slots[0])

                # Find empty slot in target cell
                tgt_empty = np.where(sg[tr, tc] == SPECIES_EMPTY)[0]
                if len(tgt_empty) == 0:
                    continue
                ts = int(tgt_empty[0])

                # Move
                sg[tr, tc, ts] = sg[sr, sc, ss]
                oa[tr, tc, ts] = oa[sr, sc, ss]
                sg[sr, sc, ss] = SPECIES_EMPTY
                oa[sr, sc, ss] = 0.0
                movers[sr, sc, ss] = False

    # ── Phase 4: Consumption ──────────────────────────────────────────────────

    def _phase_consumption(self) -> None:
        """Consumption phase: organisms consume resources or prey.

        Plants: absorb resources (biomass) from the cell.
        Prey: consume plant biomass → gain energy.
        Predators: consume prey → gain energy (Holling Type II approx).
        """
        sg = self._state["species_grid"]
        oa = self._state["organism_attrs"]
        resources = self._state["resources"]

        # Plants: absorb biomass → energy
        plant_mask = sg == SPECIES_PLANT
        if plant_mask.any():
            biomass_available = resources[:, :, 0]
            n_plants = plant_mask.sum(axis=2).astype(np.float32)
            # Each plant gets an equal share
            share = np.where(
                n_plants > 0,
                biomass_available * 0.1 / np.maximum(n_plants, 1.0),
                0.0,
            )
            # Add energy to plants
            energy_gain = share[:, :, np.newaxis] * plant_mask.astype(
                np.float32,
            )
            oa[:, :, :, 1] = np.clip(
                oa[:, :, :, 1] + energy_gain, 0.0, 1.0,
            )
            # Reduce biomass
            consumption = share * n_plants * 0.05
            resources[:, :, 0] = np.clip(
                biomass_available - consumption, 0.0, 1.0,
            )

        # Prey: consume plant biomass → gain energy
        prey_mask = sg == SPECIES_PREY
        if prey_mask.any():
            biomass = resources[:, :, 0]
            n_prey = prey_mask.sum(axis=2).astype(np.float32)
            # Holling Type II: C = aN/(1+ahN), simplified
            a = 0.3  # attack rate
            h = 0.1  # handling time
            available = biomass
            consumed = np.where(
                n_prey > 0,
                a * available / (1.0 + a * h * n_prey),
                0.0,
            )
            energy_per_prey = np.where(
                n_prey > 0, consumed * 0.8 / np.maximum(n_prey, 1.0), 0.0,
            )
            oa[:, :, :, 1] = np.clip(
                oa[:, :, :, 1]
                + energy_per_prey[:, :, np.newaxis]
                * prey_mask.astype(np.float32),
                0.0,
                1.0,
            )
            resources[:, :, 0] = np.clip(biomass - consumed, 0.0, 1.0)

        # Predators: consume prey → gain energy
        pred_mask = sg == SPECIES_PREDATOR
        if pred_mask.any():
            n_prey_per_cell = prey_mask.sum(axis=2).astype(np.float32)
            n_pred = pred_mask.sum(axis=2).astype(np.float32)
            # Each predator captures prey probabilistically
            catch_rate = np.where(
                n_prey_per_cell > 0,
                np.minimum(0.3 * n_prey_per_cell / np.maximum(n_pred, 1.0), 1.0),
                0.0,
            )
            energy_from_prey = catch_rate * 0.7  # consumption efficiency
            oa[:, :, :, 1] = np.clip(
                oa[:, :, :, 1]
                + energy_from_prey[:, :, np.newaxis]
                * pred_mask.astype(np.float32),
                0.0,
                1.0,
            )

    # ── Phase 5: Reproduction ─────────────────────────────────────────────────

    def _phase_reproduction(self) -> None:
        """Reproduction: organisms with sufficient energy may reproduce.

        Sigmoid probability: p = 1/(1 + exp(-k(E - threshold))).
        New organism placed in an empty slot in the same cell.
        Vectorized: identify reproducers and cells with empty slots,
        then batch-assign offspring.
        """
        sg = self._state["species_grid"]
        oa = self._state["organism_attrs"]
        threshold = self._params.reproduction_threshold

        for species_id in (SPECIES_PLANT, SPECIES_PREY, SPECIES_PREDATOR):
            mask = sg == species_id
            if not mask.any():
                continue

            energy = oa[:, :, :, 1]
            # Sigmoid reproduction probability
            k = 10.0
            prob = 1.0 / (1.0 + np.exp(-k * (energy - threshold)))
            reproduce = mask & (
                self._rng.random(mask.shape).astype(np.float32) < prob
            )

            if not reproduce.any():
                continue

            # Cells that have reproducers AND empty slots
            has_reproducer = np.any(reproduce, axis=2)
            has_empty = np.any(sg == SPECIES_EMPTY, axis=2)
            candidate_cells = has_reproducer & has_empty

            if not candidate_cells.any():
                continue

            cell_rows, cell_cols = np.where(candidate_cells)
            for idx in range(len(cell_rows)):
                r, c = int(cell_rows[idx]), int(cell_cols[idx])
                # Find first reproducer
                repro_slots = np.where(reproduce[r, c])[0]
                if len(repro_slots) == 0:
                    continue
                s = int(repro_slots[0])
                # Find first empty slot
                empty_slots = np.where(sg[r, c] == SPECIES_EMPTY)[0]
                if len(empty_slots) == 0:
                    continue
                ns = int(empty_slots[0])

                # Create offspring
                sg[r, c, ns] = species_id
                oa[r, c, ns, 0] = 0.8  # health
                oa[r, c, ns, 1] = 0.4  # energy (child)
                oa[r, c, ns, 2] = 0.0  # age
                # Parent loses energy
                oa[r, c, s, 1] *= 0.5

    # ── Phase 6: Mortality ────────────────────────────────────────────────────

    def _phase_mortality(self) -> None:
        """Mortality: organisms die from age, starvation, or low health.

        - Metabolic cost: energy -= metabolic_rate per tick
        - Age increment: age += 1.0
        - Death conditions: energy <= 0, health <= 0, or age > max_age
        """
        sg = self._state["species_grid"]
        oa = self._state["organism_attrs"]
        alive = sg != SPECIES_EMPTY

        if not alive.any():
            return

        # Metabolic cost
        oa[:, :, :, 1] -= self._params.metabolic_rate * alive.astype(
            np.float32,
        )

        # Age increment
        oa[:, :, :, 2] += alive.astype(np.float32)

        # Health decay (slow)
        oa[:, :, :, 0] -= 0.001 * alive.astype(np.float32)

        # Death: energy depleted
        starved = alive & (oa[:, :, :, 1] <= 0.0)
        sg[starved] = SPECIES_EMPTY
        oa[starved] = 0.0

        # Death: health depleted
        dead_health = alive & (oa[:, :, :, 0] <= 0.0)
        sg[dead_health] = SPECIES_EMPTY
        oa[dead_health] = 0.0

        # Death: old age (prey)
        prey_old = (sg == SPECIES_PREY) & (
            oa[:, :, :, 2] > self._params.max_age_prey
        )
        sg[prey_old] = SPECIES_EMPTY
        oa[prey_old] = 0.0

        # Death: old age (predator)
        pred_old = (sg == SPECIES_PREDATOR) & (
            oa[:, :, :, 2] > self._params.max_age_predator
        )
        sg[pred_old] = SPECIES_EMPTY
        oa[pred_old] = 0.0

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
