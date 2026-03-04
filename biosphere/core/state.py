"""Core simulation state definitions.

Defines GridState, constants, Intervention, and InterventionType
per BLU-002 §2.1 and §2.3. No dependencies on other biosphere.* modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TypedDict

import numpy as np

# ── Grid Constants ────────────────────────────────────────────────────────────
GRID_H: int = 50
GRID_W: int = 50
MAX_PER_CELL: int = 8

# ── Species IDs (uint8-encoded) ───────────────────────────────────────────────
SPECIES_EMPTY: int = 0
SPECIES_PLANT: int = 1
SPECIES_PREY: int = 2
SPECIES_PREDATOR: int = 3
NUM_SPECIES: int = 4


class GridState(TypedDict):
    """Complete simulation state as contiguous NumPy arrays.

    Uses mixed-dtype strategy: integer-semantic fields use integer
    dtypes, floating-point fields use float32.
    """

    # Shape: (GRID_H, GRID_W, 3), dtype float32
    # Channels: [elevation (0.0–1.0), temperature (-20–50 °C), humidity (0.0–1.0)]
    terrain: np.ndarray

    # Shape: (GRID_H, GRID_W, MAX_PER_CELL), dtype uint8
    # Values: species_id ∈ {0, 1, 2, 3}
    species_grid: np.ndarray

    # Shape: (GRID_H, GRID_W, MAX_PER_CELL, 3), dtype float32
    # Channels: [health (0.0–1.0), energy (0.0–1.0), age (ticks as float, ≥0)]
    organism_attrs: np.ndarray

    # Shape: (GRID_H, GRID_W, 2), dtype float32
    # Channels: [plant_biomass (0.0–1.0), water_availability (0.0–1.0)]
    resources: np.ndarray

    # Shape: (GRID_H, GRID_W, 2), dtype float32
    # Channels: [precipitation (0.0–1.0), sunlight (0.0–1.0)]
    weather: np.ndarray


# ── Interventions ─────────────────────────────────────────────────────────────


class InterventionType(IntEnum):
    """Domain-level intervention types for the RL agent."""

    NO_OP = 0
    SEED_PLANTS = 1
    ADJUST_PRECIPITATION = 2
    CULL_SPECIES = 3


@dataclass(frozen=True)
class Intervention:
    """A single domain-level intervention applied before a simulation tick.

    Attributes:
        type: The kind of intervention.
        region_row: Top-left row of 10×10 target region. [0, GRID_H-10].
        region_col: Top-left col of 10×10 target region. [0, GRID_W-10].
        intensity: Normalized intensity. [0.0, 1.0].
        target_species: Species ID for CULL_SPECIES. Ignored for other types.
    """

    type: InterventionType
    region_row: int
    region_col: int
    intensity: float
    target_species: int = SPECIES_EMPTY

    def validate(self) -> None:
        """Validate all fields are within legal ranges.

        Raises:
            InterventionError: If any field is out of range.
        """
        from biosphere.core.errors import InterventionError

        if self.type not in InterventionType.__members__.values():
            raise InterventionError(
                f"Invalid intervention type: {self.type}"
            )
        if not (0 <= self.region_row <= GRID_H - 10):
            raise InterventionError(
                f"region_row {self.region_row} out of range "
                f"[0, {GRID_H - 10}]"
            )
        if not (0 <= self.region_col <= GRID_W - 10):
            raise InterventionError(
                f"region_col {self.region_col} out of range "
                f"[0, {GRID_W - 10}]"
            )
        if not (0.0 <= self.intensity <= 1.0):
            raise InterventionError(
                f"intensity {self.intensity} out of range [0.0, 1.0]"
            )
        if (
            self.type == InterventionType.CULL_SPECIES
            and self.target_species
            not in (SPECIES_PREY, SPECIES_PREDATOR)
        ):
            raise InterventionError(
                f"target_species {self.target_species} invalid for "
                f"CULL_SPECIES (must be PREY or PREDATOR)"
            )
