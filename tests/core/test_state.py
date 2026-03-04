"""Tests for biosphere.core.state — GridState, constants, Intervention.

Refs: EVO-001, BLU-002 §2.1, §2.3
"""

from __future__ import annotations

import numpy as np
import pytest

from biosphere.core.errors import InterventionError
from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    NUM_SPECIES,
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
    Intervention,
    InterventionType,
)


class TestConstants:
    """Grid and species constants match BLU-002 §2.1."""

    def test_grid_dimensions(self) -> None:
        """Grid is 50x50."""
        assert GRID_H == 50
        assert GRID_W == 50

    def test_max_per_cell(self) -> None:
        """8 organism slots per cell."""
        assert MAX_PER_CELL == 8

    def test_species_ids_unique(self) -> None:
        """Species IDs are distinct integers."""
        ids = [SPECIES_EMPTY, SPECIES_PLANT, SPECIES_PREY, SPECIES_PREDATOR]
        assert len(set(ids)) == NUM_SPECIES

    def test_species_empty_is_zero(self) -> None:
        """SPECIES_EMPTY == 0 (sentinel value)."""
        assert SPECIES_EMPTY == 0


class TestInterventionType:
    """InterventionType enum values."""

    def test_no_op_is_zero(self) -> None:
        """NO_OP == 0."""
        assert InterventionType.NO_OP == 0

    def test_all_types_present(self) -> None:
        """All 4 intervention types exist."""
        types = list(InterventionType)
        assert len(types) == 4


class TestIntervention:
    """Intervention dataclass with validation."""

    def test_valid_seed_plants(self) -> None:
        """Valid SEED_PLANTS intervention passes validation."""
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0,
            region_col=0,
            intensity=0.5,
        )
        iv.validate()  # should not raise

    def test_valid_cull_prey(self) -> None:
        """Valid CULL_SPECIES targeting prey passes validation."""
        iv = Intervention(
            type=InterventionType.CULL_SPECIES,
            region_row=20,
            region_col=30,
            intensity=0.3,
            target_species=SPECIES_PREY,
        )
        iv.validate()  # should not raise

    def test_invalid_region_row(self) -> None:
        """Out-of-range region_row raises InterventionError."""
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=GRID_H,  # too high
            region_col=0,
            intensity=0.5,
        )
        with pytest.raises(InterventionError, match="region_row"):
            iv.validate()

    def test_invalid_region_col(self) -> None:
        """Out-of-range region_col raises InterventionError."""
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0,
            region_col=GRID_W,  # too high
            intensity=0.5,
        )
        with pytest.raises(InterventionError, match="region_col"):
            iv.validate()

    def test_invalid_intensity(self) -> None:
        """Out-of-range intensity raises InterventionError."""
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0,
            region_col=0,
            intensity=1.5,
        )
        with pytest.raises(InterventionError, match="intensity"):
            iv.validate()

    def test_cull_requires_valid_species(self) -> None:
        """CULL_SPECIES with EMPTY target fails validation."""
        iv = Intervention(
            type=InterventionType.CULL_SPECIES,
            region_row=0,
            region_col=0,
            intensity=0.5,
            target_species=SPECIES_EMPTY,
        )
        with pytest.raises(InterventionError, match="target_species"):
            iv.validate()

    def test_frozen_dataclass(self) -> None:
        """Intervention is immutable (frozen=True)."""
        iv = Intervention(
            type=InterventionType.NO_OP,
            region_row=0,
            region_col=0,
            intensity=0.0,
        )
        with pytest.raises(AttributeError):
            iv.intensity = 0.5  # type: ignore[misc]

    def test_max_valid_region(self) -> None:
        """Maximum valid region coordinates pass validation."""
        iv = Intervention(
            type=InterventionType.ADJUST_PRECIPITATION,
            region_row=GRID_H - 10,
            region_col=GRID_W - 10,
            intensity=1.0,
        )
        iv.validate()  # should not raise
