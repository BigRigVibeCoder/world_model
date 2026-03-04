"""Tests for biosphere.ui — TUI widgets and payload.

Refs: EVO-002 §4.3
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

import numpy as np
import pytest

from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    SPECIES_PLANT,
)
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
    # Place some plants in first few cells
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

    def test_render_empty_grid_spaces(self) -> None:
        """Empty grid renders as spaces.

        Refs: EVO-002 §4.3
        """
        sg = np.zeros((GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8)
        result = GridWidget.render_to_string(sg)
        assert result.replace("\n", "").strip() == ""
        assert len(result.split("\n")) == GRID_H


@pytest.mark.unit
class TestChartsWidget:
    """ChartsWidget bar rendering per EVO-002 §4.3."""

    def test_bar_line_nonempty(self) -> None:
        """_bar_line produces non-empty formatted string.

        Refs: EVO-002 §4.3
        """
        bar = ChartsWidget._bar_line("🌱 Plants", 100, 200, "green")
        assert "100" in bar
        assert "Plants" in bar

    def test_bar_line_zero_total(self) -> None:
        """_bar_line handles zero total without crashing.

        Refs: EVO-002 §4.3
        """
        bar = ChartsWidget._bar_line("🐇 Prey", 0, 0, "blue")
        assert "0" in bar
        assert "Prey" in bar
