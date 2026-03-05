"""Extracted simulation phase functions per GOV-003 §4.1.

Six-phase vectorized update cycle, split from SimulationEngine
for file-size compliance (≤500 lines per file).

Each function mutates state arrays in-place for performance.

READING GUIDE FOR INCIDENT RESPONDERS:
  1. If organisms stop moving          → check phase_movement() and MOVEMENT_PROBABILITY
  2. If population explodes/collapses  → check phase_reproduction() thresholds and _spawn_offspring()
  3. If resources are infinite/zero    → check phase_resource_growth() logistic params
  4. If weather is uniform/frozen      → check phase_weather_diffusion() sigma value
  5. If mass die-offs occur           → check phase_mortality() and _apply_death()
  6. If C extension causes corruption → set native.HAS_C_EXTENSION = False to force Python fallback
  7. If NaN appears in arrays         → C extension may be writing OOB; check _phases_c.c bounds

REF: BLU-001 §4 (6-phase design)
REF: DEF-001-02 (file extraction from simulation.py)
SEE ALSO: simulation.py — orchestrates these phases via phase delegates
SEE ALSO: _phases_c.c — C implementations of movement + reproduction inner loops
SEE ALSO: native.py — transparent C/Python fallback wrapper
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from scipy.ndimage import gaussian_filter  # type: ignore[import-untyped]

from biosphere.core.native import (
    HAS_C_EXTENSION,
    c_phase_movement,
    c_phase_spawn,
)

from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
    GridState,
)

# ── Constants ─────────────────────────────────────────────────────────────────

INIT_PLANT_DENSITY: float = 0.3
INIT_PREY_DENSITY: float = 0.1
INIT_PREDATOR_DENSITY: float = 0.03
MOVEMENT_PROBABILITY: float = 0.2


@runtime_checkable
class SimulationParams(Protocol):
    """Parameter protocol — mirrors SimulationEngine.SimulationParams."""

    growth_rate: float
    reproduction_threshold: float
    max_age_prey: int
    max_age_predator: int
    metabolic_rate: float
    weather_sigma: float


# ── Initialization Helpers ────────────────────────────────────────────────────


def init_terrain(rng: np.random.Generator) -> np.ndarray:
    """Generate smooth random terrain: elevation, temperature, humidity.

    Returns:
        Array of shape (H, W, 3), dtype float32.
    """
    terrain = np.zeros((GRID_H, GRID_W, 3), dtype=np.float32)
    # Elevation: smooth random
    terrain[:, :, 0] = gaussian_filter(
        rng.random((GRID_H, GRID_W), dtype=np.float32), sigma=5.0,
    )
    # Temperature: gradient + noise
    terrain[:, :, 1] = np.linspace(
        20.0, 35.0, GRID_H, dtype=np.float32,
    )[:, np.newaxis] + rng.normal(
        0, 2, (GRID_H, GRID_W),
    ).astype(np.float32)
    # Humidity: clamped smooth random
    terrain[:, :, 2] = np.clip(
        gaussian_filter(
            rng.random((GRID_H, GRID_W), dtype=np.float32), sigma=3.0,
        ),
        0.0, 1.0,
    )
    assert terrain.shape == (GRID_H, GRID_W, 3), "terrain shape invariant"
    assert terrain.dtype == np.float32, "terrain dtype invariant"
    return terrain


def init_organisms(
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Populate initial species grid and organism attributes.

    Returns:
        (species_grid, organism_attrs) arrays.
    """
    species_grid = np.zeros(
        (GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8,
    )
    # Plants: ~30% density
    plant_mask = rng.random((GRID_H, GRID_W)) < INIT_PLANT_DENSITY
    for row, col in zip(*np.where(plant_mask), strict=True):
        n_plants = rng.integers(1, 4)
        species_grid[row, col, :n_plants] = SPECIES_PLANT

    # Prey: ~10% density
    prey_mask = rng.random((GRID_H, GRID_W)) < INIT_PREY_DENSITY
    for row, col in zip(*np.where(prey_mask), strict=True):
        empty_slots = np.where(species_grid[row, col] == SPECIES_EMPTY)[0]
        if len(empty_slots) > 0:
            species_grid[row, col, empty_slots[0]] = SPECIES_PREY

    # Predators: ~3% density
    pred_mask = rng.random((GRID_H, GRID_W)) < INIT_PREDATOR_DENSITY
    for row, col in zip(*np.where(pred_mask), strict=True):
        empty_slots = np.where(species_grid[row, col] == SPECIES_EMPTY)[0]
        if len(empty_slots) > 0:
            species_grid[row, col, empty_slots[0]] = SPECIES_PREDATOR

    # Organism attributes: health, energy, age
    organism_attrs = np.zeros(
        (GRID_H, GRID_W, MAX_PER_CELL, 3), dtype=np.float32,
    )
    alive_mask = species_grid > SPECIES_EMPTY
    n_alive = int(alive_mask.sum())
    organism_attrs[alive_mask, 0] = rng.uniform(
        0.5, 1.0, size=n_alive,
    ).astype(np.float32)  # health
    organism_attrs[alive_mask, 1] = rng.uniform(
        0.3, 0.8, size=n_alive,
    ).astype(np.float32)  # energy
    organism_attrs[alive_mask, 2] = rng.uniform(
        0.0, 50.0, size=n_alive,
    ).astype(np.float32)  # age

    assert species_grid.shape == (GRID_H, GRID_W, MAX_PER_CELL)
    assert organism_attrs.shape == (GRID_H, GRID_W, MAX_PER_CELL, 3)
    return species_grid, organism_attrs


def init_resources(
    terrain: np.ndarray, rng: np.random.Generator,
) -> np.ndarray:
    """Generate initial resources correlated with terrain humidity.

    Returns:
        Array of shape (H, W, 2), dtype float32.
    """
    resources = np.zeros((GRID_H, GRID_W, 2), dtype=np.float32)
    resources[:, :, 0] = np.clip(
        terrain[:, :, 2] * 0.8
        + rng.normal(0, 0.1, (GRID_H, GRID_W)).astype(np.float32),
        0.0, 1.0,
    )  # plant_biomass
    resources[:, :, 1] = np.clip(
        terrain[:, :, 2] * 0.9
        + rng.normal(0, 0.05, (GRID_H, GRID_W)).astype(np.float32),
        0.0, 1.0,
    )  # water
    assert resources.shape == (GRID_H, GRID_W, 2)
    return resources


# ── Phase 1: Weather Diffusion ────────────────────────────────────────────────


def phase_weather_diffusion(
    state: GridState, params: SimulationParams, rng: np.random.Generator,
) -> None:
    """Spatially diffuse weather patterns using Gaussian blur."""
    sigma = params.weather_sigma
    if sigma > 0.0:
        weather = state["weather"]
        noise = rng.normal(0, 0.02, weather.shape).astype(np.float32)
        weather += noise
        for ch in range(weather.shape[2]):
            weather[:, :, ch] = gaussian_filter(
                weather[:, :, ch], sigma=sigma,
            ).astype(np.float32)
        np.clip(weather, 0.0, 1.0, out=weather)


# ── Phase 2: Resource Growth ─────────────────────────────────────────────────


def phase_resource_growth(
    state: GridState, params: SimulationParams,
) -> None:
    """Logistic resource growth: dP/dt = rP(1 - P/K).

    Plant biomass grows modulated by sunlight.
    Water replenishes from precipitation.
    """
    r = params.growth_rate
    resources = state["resources"]
    weather = state["weather"]

    sunlight = weather[:, :, 1]
    biomass = resources[:, :, 0]
    growth = r * biomass * (1.0 - biomass) * sunlight
    resources[:, :, 0] = np.clip(biomass + growth, 0.0, 1.0)

    precip = weather[:, :, 0]
    water = resources[:, :, 1]
    water_delta = 0.1 * precip - 0.05
    resources[:, :, 1] = np.clip(water + water_delta, 0.0, 1.0)


# ── Phase 3: Movement ────────────────────────────────────────────────────────


def phase_movement(
    state: GridState, rng: np.random.Generator,
) -> None:
    """Random neighbor migration for prey and predators.

    ~20% of mobile organisms attempt migration each tick.
    Plants do not move.

    PRECONDITION:  state arrays must be valid GridState (no NaN).
    POSTCONDITION: organism count is conserved (no creation/destruction).
    SIDE EFFECTS:  Mutates species_grid and organism_attrs in-place.
    THREAD SAFETY: Not thread-safe. Caller must hold simulation lock.

    FAILURE MODE: If this function silently fails, organisms freeze in place.
    BLAST RADIUS: Ecosystem diverges — predators starve, prey overpopulate.
    MITIGATION:   Detected indirectly via population metrics in RL reward.
    SEE ALSO:     _phases_c.c:phase_movement_c() — C implementation
    """
    sg = state["species_grid"]
    oa = state["organism_attrs"]

    if HAS_C_EXTENSION:
        # DECISION: Use a CPython C extension instead of Numba JIT or Cython.
        # ALTERNATIVES CONSIDERED: Numba @njit (GIL issues with NumPy 2.x),
        #   Cython (build complexity, separate .pyx files).
        # TRADEOFF: Requires GCC at build time, but 4× throughput gain and
        #   zero runtime dependencies beyond NumPy.
        # REF: BLU-001 §4.3 (performance target: ≥1000 steps/sec)
        rand_arr = rng.random(
            sg.shape, dtype=np.float32,
        )
        dir_arr = rng.integers(
            0, 4, size=sg.shape, dtype=np.int32,
        )
        for species_id in (SPECIES_PREY, SPECIES_PREDATOR):
            c_phase_movement(
                sg, oa, GRID_H, GRID_W, MAX_PER_CELL,
                species_id, MOVEMENT_PROBABILITY,
                rand_arr, dir_arr,
            )
        return

    # Pure Python fallback (original implementation)
    for species_id in (SPECIES_PREY, SPECIES_PREDATOR):
        mask = sg == species_id
        if not mask.any():
            continue

        movers = mask & (
            rng.random(mask.shape).astype(np.float32) < MOVEMENT_PROBABILITY
        )
        if not movers.any():
            continue

        mover_cells = np.any(movers, axis=2)
        if not mover_cells.any():
            continue

        cell_rows, cell_cols = np.where(mover_cells)
        n_movers = len(cell_rows)

        dirs = rng.integers(0, 4, size=n_movers)
        dr = np.array([-1, 1, 0, 0])[dirs]
        dc = np.array([0, 0, -1, 1])[dirs]
        target_rows = cell_rows + dr
        target_cols = cell_cols + dc

        valid = (
            (target_rows >= 0) & (target_rows < GRID_H)
            & (target_cols >= 0) & (target_cols < GRID_W)
        )

        for idx in np.where(valid)[0]:
            sr, sc = int(cell_rows[idx]), int(cell_cols[idx])
            tr, tc = int(target_rows[idx]), int(target_cols[idx])

            src_slots = np.where(movers[sr, sc])[0]
            if len(src_slots) == 0:
                continue
            ss = int(src_slots[0])

            tgt_empty = np.where(sg[tr, tc] == SPECIES_EMPTY)[0]
            if len(tgt_empty) == 0:
                continue
            ts = int(tgt_empty[0])

            sg[tr, tc, ts] = sg[sr, sc, ss]
            oa[tr, tc, ts] = oa[sr, sc, ss]
            sg[sr, sc, ss] = SPECIES_EMPTY
            oa[sr, sc, ss] = 0.0
            movers[sr, sc, ss] = False


# ── Phase 4: Consumption ─────────────────────────────────────────────────────


def phase_consumption(state: GridState) -> None:
    """Consumption: organisms consume resources or prey.

    Plants absorb biomass. Prey eat plants. Predators eat prey.
    Uses Holling Type II functional response for prey/predator.
    """
    sg = state["species_grid"]
    oa = state["organism_attrs"]
    resources = state["resources"]

    _consume_plants(sg, oa, resources)
    _consume_prey(sg, oa, resources)
    _consume_predators(sg, oa)


def _consume_plants(
    sg: np.ndarray, oa: np.ndarray, resources: np.ndarray,
) -> None:
    """Plants absorb biomass → gain energy."""
    plant_mask = sg == SPECIES_PLANT
    if not plant_mask.any():
        return
    biomass_available = resources[:, :, 0]
    n_plants = plant_mask.sum(axis=2).astype(np.float32)
    share = np.where(
        n_plants > 0,
        biomass_available * 0.1 / np.maximum(n_plants, 1.0), 0.0,
    )
    energy_gain = share[:, :, np.newaxis] * plant_mask.astype(np.float32)
    oa[:, :, :, 1] = np.clip(oa[:, :, :, 1] + energy_gain, 0.0, 1.0)
    consumption = share * n_plants * 0.05
    resources[:, :, 0] = np.clip(
        biomass_available - consumption, 0.0, 1.0,
    )


def _consume_prey(
    sg: np.ndarray, oa: np.ndarray, resources: np.ndarray,
) -> None:
    """Prey consume plant biomass → gain energy (Holling Type II)."""
    prey_mask = sg == SPECIES_PREY
    if not prey_mask.any():
        return
    biomass = resources[:, :, 0]
    n_prey = prey_mask.sum(axis=2).astype(np.float32)
    a = 0.3  # attack rate
    h = 0.1  # handling time
    consumed = np.where(
        n_prey > 0, a * biomass / (1.0 + a * h * n_prey), 0.0,
    )
    energy_per_prey = np.where(
        n_prey > 0, consumed * 0.8 / np.maximum(n_prey, 1.0), 0.0,
    )
    oa[:, :, :, 1] = np.clip(
        oa[:, :, :, 1]
        + energy_per_prey[:, :, np.newaxis] * prey_mask.astype(np.float32),
        0.0, 1.0,
    )
    resources[:, :, 0] = np.clip(biomass - consumed, 0.0, 1.0)


def _consume_predators(sg: np.ndarray, oa: np.ndarray) -> None:
    """Predators consume prey → gain energy."""
    prey_mask = sg == SPECIES_PREY
    pred_mask = sg == SPECIES_PREDATOR
    if not pred_mask.any():
        return
    n_prey_per_cell = prey_mask.sum(axis=2).astype(np.float32)
    n_pred = pred_mask.sum(axis=2).astype(np.float32)
    catch_rate = np.where(
        n_prey_per_cell > 0,
        np.minimum(0.3 * n_prey_per_cell / np.maximum(n_pred, 1.0), 1.0),
        0.0,
    )
    energy_from_prey = catch_rate * 0.7
    oa[:, :, :, 1] = np.clip(
        oa[:, :, :, 1]
        + energy_from_prey[:, :, np.newaxis] * pred_mask.astype(np.float32),
        0.0, 1.0,
    )


# ── Phase 5: Reproduction ────────────────────────────────────────────────────


def phase_reproduction(
    state: GridState, params: SimulationParams,
    rng: np.random.Generator,
) -> None:
    """Reproduction: sigmoid probability based on energy.

    p = 1/(1 + exp(-k(E - threshold))).
    Offspring placed in empty slot in same cell.
    """
    sg = state["species_grid"]
    oa = state["organism_attrs"]
    threshold = params.reproduction_threshold

    for species_id in (SPECIES_PLANT, SPECIES_PREY, SPECIES_PREDATOR):
        mask = sg == species_id
        if not mask.any():
            continue

        energy = oa[:, :, :, 1]
        k = 10.0
        prob = 1.0 / (1.0 + np.exp(-k * (energy - threshold)))
        reproduce = mask & (
            rng.random(mask.shape).astype(np.float32) < prob
        )
        if not reproduce.any():
            continue

        _spawn_offspring(sg, oa, reproduce, species_id)


def _spawn_offspring(
    sg: np.ndarray, oa: np.ndarray,
    reproduce: np.ndarray, species_id: int,
) -> None:
    """Place offspring in empty slots of reproducing cells.

    PRECONDITION:  reproduce must be a bool/uint8 mask same shape as sg.
    POSTCONDITION: New organisms have health=0.8, energy=0.4, age=0.
                   Parent energy is halved (×0.5).
    SIDE EFFECTS:  Mutates sg and oa in-place.
    SEE ALSO:      _phases_c.c:phase_spawn_offspring_c() — C implementation
    """
    if HAS_C_EXTENSION:
        # REF: BLU-001 §4.3 — C extension for reproduction inner loop
        c_phase_spawn(
            sg, oa, reproduce.view(np.uint8),
            GRID_H, GRID_W, MAX_PER_CELL, species_id,
        )
        return

    # Pure Python fallback
    has_reproducer = np.any(reproduce, axis=2)
    has_empty = np.any(sg == SPECIES_EMPTY, axis=2)
    candidate_cells = has_reproducer & has_empty
    if not candidate_cells.any():
        return

    cell_rows, cell_cols = np.where(candidate_cells)

    for idx in range(len(cell_rows)):
        r, c = int(cell_rows[idx]), int(cell_cols[idx])
        repro_slots = np.where(reproduce[r, c])[0]
        if len(repro_slots) == 0:
            continue
        s = int(repro_slots[0])
        empty_slots = np.where(sg[r, c] == SPECIES_EMPTY)[0]
        if len(empty_slots) == 0:
            continue
        ns = int(empty_slots[0])

        sg[r, c, ns] = species_id
        oa[r, c, ns, 0] = 0.8  # health
        oa[r, c, ns, 1] = 0.4  # energy (child)
        oa[r, c, ns, 2] = 0.0  # age
        oa[r, c, s, 1] *= 0.5  # parent energy cost


# ── Phase 6: Mortality ────────────────────────────────────────────────────────


def phase_mortality(
    state: GridState, params: SimulationParams,
) -> None:
    """Mortality: organisms die from age, starvation, or low health.

    Metabolic cost: energy -= metabolic_rate per tick.
    Age increment: age += 1.0 per tick.
    Death conditions: energy ≤ 0, health ≤ 0, or age > max_age.
    """
    sg = state["species_grid"]
    oa = state["organism_attrs"]
    alive = sg != SPECIES_EMPTY

    if not alive.any():
        return

    # Metabolic cost
    oa[:, :, :, 1] -= params.metabolic_rate * alive.astype(np.float32)
    # Age increment
    oa[:, :, :, 2] += alive.astype(np.float32)
    # Health decay
    oa[:, :, :, 0] -= 0.001 * alive.astype(np.float32)

    _apply_death(sg, oa, alive, params)


def _apply_death(
    sg: np.ndarray, oa: np.ndarray,
    alive: np.ndarray, params: SimulationParams,
) -> None:
    """Remove dead organisms from the grid."""
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
        oa[:, :, :, 2] > params.max_age_prey
    )
    sg[prey_old] = SPECIES_EMPTY
    oa[prey_old] = 0.0

    # Death: old age (predator)
    pred_old = (sg == SPECIES_PREDATOR) & (
        oa[:, :, :, 2] > params.max_age_predator
    )
    sg[pred_old] = SPECIES_EMPTY
    oa[pred_old] = 0.0
