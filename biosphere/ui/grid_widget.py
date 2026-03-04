"""Grid widget for TUI — renders species grid with colored characters.

Uses dots (●) for organisms on a dark background, creating
a simulation-style visualization similar to cellular automata.

Refs: EVO-002 §4.3, BLU-001 §7.5
"""

from __future__ import annotations

import numpy as np
from textual.widgets import Static

from biosphere.core.state import (
    GRID_H,
    GRID_W,
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
)
from biosphere.ui.payload import RenderPayload

# ── Visual Mapping ────────────────────────────────────────────────────────────

SPECIES_CHAR: dict[int, str] = {
    SPECIES_EMPTY: "·",
    SPECIES_PLANT: "●",
    SPECIES_PREY: "●",
    SPECIES_PREDATOR: "●",
}

SPECIES_COLOR: dict[int, str] = {
    SPECIES_EMPTY: "#333333",
    SPECIES_PLANT: "#00cc44",
    SPECIES_PREY: "#ffcc00",
    SPECIES_PREDATOR: "#ff3333",
}


class GridWidget(Static):
    """Renders the 50×50 species grid using colored Rich markup.

    Each cell shows the highest-trophic species as a colored dot.
    Empty cells show a dim dot for grid visibility.

    Refs: EVO-002 §4.3
    """

    DEFAULT_CSS = """
    GridWidget {
        width: 100%;
        height: 100%;
        text-style: bold;
        background: #0a0a0a;
        padding: 0 1;
    }
    """

    def update_grid(self, payload: RenderPayload) -> None:
        """Update the grid display from a RenderPayload."""
        sg = payload.species_grid
        lines: list[str] = []

        for r in range(GRID_H):
            row_parts: list[str] = []
            for c in range(GRID_W):
                max_species = int(sg[r, c].max())
                char = SPECIES_CHAR.get(max_species, "?")
                color = SPECIES_COLOR.get(max_species, "white")
                row_parts.append(f"[{color}]{char}[/]")
            lines.append("".join(row_parts))

        self.update("\n".join(lines))

    @staticmethod
    def render_to_string(species_grid: np.ndarray) -> str:
        """Render grid to plain ANSI string (for testing).

        Refs: EVO-002 §4.3
        """
        lines: list[str] = []
        for r in range(min(GRID_H, species_grid.shape[0])):
            row_chars: list[str] = []
            for c in range(min(GRID_W, species_grid.shape[1])):
                max_species = int(species_grid[r, c].max())
                row_chars.append(SPECIES_CHAR.get(max_species, "?"))
            lines.append("".join(row_chars))
        return "\n".join(lines)
