"""Tests for biosphere.ui — TUI widgets and payload.

Refs: EVO-002 §4.3
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

import numpy as np
import pytest

from biosphere.core.simulation import SimulationEngine
from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
)
from biosphere.infrastructure.config import SimulationConfig
from biosphere.ui.charts_widget import ChartsWidget
from biosphere.ui.grid_widget import GridWidget
from biosphere.ui.payload import RenderPayload


def _make_payload(
    tick: int = 0,
    n_plants: int = 100,
    n_prey: int = 50,
    n_pred: int = 10,
) -> RenderPayload:
    """Create a test RenderPayload."""
    sg = np.zeros((GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8)
    placed = 0
    for r in range(GRID_H):
        for c in range(GRID_W):
            if placed < n_plants:
                sg[r, c, 0] = SPECIES_PLANT
                placed += 1

    return RenderPayload(
        tick=tick,
        species_grid=sg,
        n_plants=n_plants,
        n_prey=n_prey,
        n_predators=n_pred,
        mean_health=0.7,
        mean_energy=0.5,
        mean_precipitation=0.4,
        mean_sunlight=0.6,
        entropy=0.8,
        reward=0.5,
        paused=False,
    )


@pytest.mark.unit
class TestRenderPayload:
    """RenderPayload dataclass per EVO-002 §4.3."""

    def test_payload_creation(self) -> None:
        """Payload stores all required fields.

        Refs: EVO-002 §4.3
        """
        p = _make_payload(tick=42, n_plants=100, n_prey=50, n_pred=10)
        assert p.tick == 42
        assert p.n_plants == 100
        assert p.n_prey == 50
        assert p.n_predators == 10

    def test_payload_frozen(self) -> None:
        """Payload is immutable (frozen=True).

        Refs: EVO-002 §4.3
        """
        p = _make_payload()
        with pytest.raises(AttributeError):
            p.tick = 99  # type: ignore[misc]
        assert p.tick == 0

    def test_payload_from_engine_state(self) -> None:
        """Payload can be built from live engine state.

        Refs: EVO-002 §4.3, BLU-002 §2.2
        """
        engine = SimulationEngine(SimulationConfig())
        state = engine.step()
        sg = state["species_grid"]
        oa = state["organism_attrs"]
        weather = state["weather"]

        alive = sg != SPECIES_EMPTY
        payload = RenderPayload(
            tick=engine.tick,
            species_grid=sg,
            n_plants=int((sg == SPECIES_PLANT).sum()),
            n_prey=int((sg == SPECIES_PREY).sum()),
            n_predators=int((sg == SPECIES_PREDATOR).sum()),
            mean_health=float(oa[:, :, :, 0][alive].mean()) if alive.any() else 0.0,
            mean_energy=float(oa[:, :, :, 1][alive].mean()) if alive.any() else 0.0,
            mean_precipitation=float(weather[:, :, 0].mean()),
            mean_sunlight=float(weather[:, :, 1].mean()),
            entropy=0.8,
            reward=0.5,
            paused=False,
        )

        assert payload.tick == 1
        assert payload.n_plants > 0
        assert payload.mean_health > 0


@pytest.mark.unit
class TestGridWidget:
    """GridWidget rendering per EVO-002 §4.3."""

    def test_render_to_string_correct_size(self) -> None:
        """Render produces GRID_H lines of GRID_W characters.

        Refs: EVO-002 §4.3
        """
        sg = np.zeros((GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8)
        result = GridWidget.render_to_string(sg)
        lines = result.split("\n")
        assert len(lines) == GRID_H
        assert len(lines[0]) == GRID_W

    def test_render_empty_grid_dots(self) -> None:
        """Empty grid renders as dim dots.

        Refs: EVO-002 §4.3
        """
        sg = np.zeros((GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8)
        result = GridWidget.render_to_string(sg)
        # All chars should be the empty dot
        assert all(c in ("\u00b7", "\n") for c in result)
        assert len(result.split("\n")) == GRID_H

    def test_render_populated_grid_has_blocks(self) -> None:
        """Grid with organisms renders non-space characters.

        Refs: EVO-002 §4.3
        """
        sg = np.zeros((GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8)
        sg[0, 0, 0] = SPECIES_PLANT
        sg[10, 10, 0] = SPECIES_PREY
        sg[20, 20, 0] = SPECIES_PREDATOR
        result = GridWidget.render_to_string(sg)
        lines = result.split("\n")
        assert lines[0][0] == "\u25cf"  # ● (filled circle)
        assert lines[10][10] == "\u25cf"


@pytest.mark.unit
class TestChartsWidget:
    """ChartsWidget bar rendering per EVO-002 §4.3."""

    def test_bar_line_nonempty(self) -> None:
        """_bar_line produces non-empty formatted string.

        Refs: EVO-002 §4.3
        """
        bar = ChartsWidget._bar_line("Plants", 100, 200, "green")
        assert "100" in bar
        assert "Plants" in bar

    def test_bar_line_zero_total(self) -> None:
        """_bar_line handles zero total without crashing.

        Refs: EVO-002 §4.3
        """
        bar = ChartsWidget._bar_line("Prey", 0, 0, "blue")
        assert "0" in bar
        assert "Prey" in bar

    def test_bar_line_proportional(self) -> None:
        """Bar filled characters scale with ratio.

        Refs: EVO-002 §4.3
        """
        bar_half = ChartsWidget._bar_line("Test", 50, 100, "green")
        bar_full = ChartsWidget._bar_line("Test", 100, 100, "green")
        assert bar_full.count("█") >= bar_half.count("█")
        assert "50" in bar_half
