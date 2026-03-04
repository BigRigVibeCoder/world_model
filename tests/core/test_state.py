"""Tests for biosphere.core.state — GridState, constants, Intervention.

Refs: EVO-001, BLU-002 §2.1, §2.3
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

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


@pytest.mark.unit
class TestConstants:
    """Grid and species constants match BLU-002 §2.1."""

    def test_grid_dimensions(self) -> None:
        """Grid is 50×50 as specified in BLU-002 §2.1.

        Refs: BLU-002 §2.1
        """
        assert GRID_H == 50
        assert GRID_W == 50

    def test_max_per_cell(self) -> None:
        """8 organism slots per cell as specified in BLU-002 §2.1.

        Refs: BLU-002 §2.1
        """
        assert MAX_PER_CELL == 8
        assert MAX_PER_CELL > 0

    def test_species_ids_unique_and_ordered(self) -> None:
        """Species IDs are distinct and EMPTY=0 is the sentinel.

        Refs: BLU-002 §2.1
        """
        ids = [SPECIES_EMPTY, SPECIES_PLANT, SPECIES_PREY, SPECIES_PREDATOR]
        assert len(set(ids)) == NUM_SPECIES
        assert SPECIES_EMPTY == 0
        assert all(isinstance(i, int) for i in ids)

    def test_species_hierarchy(self) -> None:
        """Species IDs follow trophic ordering: EMPTY < PLANT < PREY < PREDATOR.

        Refs: BLU-001 §7.2
        """
        assert SPECIES_EMPTY < SPECIES_PLANT
        assert SPECIES_PLANT < SPECIES_PREY
        assert SPECIES_PREY < SPECIES_PREDATOR


@pytest.mark.unit
class TestInterventionType:
    """InterventionType enum values per BLU-002 §2.3."""

    def test_no_op_is_zero(self) -> None:
        """NO_OP == 0, used as default/skip action.

        Refs: BLU-002 §2.3
        """
        assert InterventionType.NO_OP == 0
        assert InterventionType.NO_OP.name == "NO_OP"

    def test_all_types_present(self) -> None:
        """All 4 intervention types exist with distinct values.

        Refs: BLU-002 §2.3
        """
        types = list(InterventionType)
        assert len(types) == 4
        assert len({t.value for t in types}) == 4


@pytest.mark.unit
class TestIntervention:
    """Intervention dataclass with validation per BLU-002 §2.3."""

    def test_valid_seed_plants(self) -> None:
        """Valid SEED_PLANTS intervention at origin passes validation.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0,
            region_col=0,
            intensity=0.5,
        )
        iv.validate()  # should not raise
        assert iv.type == InterventionType.SEED_PLANTS
        assert iv.intensity == 0.5

    def test_valid_cull_prey(self) -> None:
        """Valid CULL_SPECIES targeting prey passes validation.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.CULL_SPECIES,
            region_row=20,
            region_col=30,
            intensity=0.3,
            target_species=SPECIES_PREY,
        )
        iv.validate()  # should not raise
        assert iv.target_species == SPECIES_PREY
        assert iv.region_row == 20

    def test_valid_cull_predator(self) -> None:
        """Valid CULL_SPECIES targeting predator passes validation.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.CULL_SPECIES,
            region_row=10,
            region_col=10,
            intensity=0.5,
            target_species=SPECIES_PREDATOR,
        )
        iv.validate()
        assert iv.target_species == SPECIES_PREDATOR
        assert iv.type == InterventionType.CULL_SPECIES

    def test_invalid_region_row(self) -> None:
        """Out-of-range region_row raises InterventionError.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=GRID_H,
            region_col=0,
            intensity=0.5,
        )
        with pytest.raises(InterventionError, match="region_row") as exc_info:
            iv.validate()
        assert "region_row" in str(exc_info.value)

    def test_invalid_region_col(self) -> None:
        """Out-of-range region_col raises InterventionError.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0,
            region_col=GRID_W,
            intensity=0.5,
        )
        with pytest.raises(InterventionError, match="region_col") as exc_info:
            iv.validate()
        assert "region_col" in str(exc_info.value)

    def test_invalid_intensity_too_high(self) -> None:
        """Intensity > 1.0 raises InterventionError.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0,
            region_col=0,
            intensity=1.5,
        )
        with pytest.raises(InterventionError, match="intensity") as exc_info:
            iv.validate()
        assert "intensity" in str(exc_info.value)

    def test_invalid_intensity_negative(self) -> None:
        """Intensity < 0.0 raises InterventionError.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.SEED_PLANTS,
            region_row=0,
            region_col=0,
            intensity=-0.1,
        )
        with pytest.raises(InterventionError, match="intensity") as exc_info:
            iv.validate()
        assert "intensity" in str(exc_info.value)

    def test_cull_requires_valid_species(self) -> None:
        """CULL_SPECIES with EMPTY target fails validation.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.CULL_SPECIES,
            region_row=0,
            region_col=0,
            intensity=0.5,
            target_species=SPECIES_EMPTY,
        )
        with pytest.raises(InterventionError, match="target_species") as exc_info:
            iv.validate()
        assert "target_species" in str(exc_info.value)

    def test_cull_plant_invalid(self) -> None:
        """CULL_SPECIES targeting plant fails (only prey/predator allowed).

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.CULL_SPECIES,
            region_row=0,
            region_col=0,
            intensity=0.5,
            target_species=SPECIES_PLANT,
        )
        with pytest.raises(InterventionError, match="target_species") as exc_info:
            iv.validate()
        assert "target_species" in str(exc_info.value)

    def test_frozen_dataclass(self) -> None:
        """Intervention is immutable (frozen=True) per BLU-002 §2.3.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.NO_OP,
            region_row=0,
            region_col=0,
            intensity=0.0,
        )
        with pytest.raises(AttributeError):
            iv.intensity = 0.5  # type: ignore[misc]
        assert iv.intensity == 0.0

    def test_max_valid_region(self) -> None:
        """Maximum valid region coordinates pass validation.

        Refs: BLU-002 §2.3
        """
        iv = Intervention(
            type=InterventionType.ADJUST_PRECIPITATION,
            region_row=GRID_H - 10,
            region_col=GRID_W - 10,
            intensity=1.0,
        )
        iv.validate()
        assert iv.region_row == GRID_H - 10
        assert iv.region_col == GRID_W - 10
