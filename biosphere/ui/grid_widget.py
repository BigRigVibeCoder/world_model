"""Grid widget for TUI — renders 50×50 species grid with Rich markup.

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

# ── Color Mapping ─────────────────────────────────────────────────────────────

SPECIES_CHAR: dict[int, str] = {
    SPECIES_EMPTY: " ",
    SPECIES_PLANT: "█",
    SPECIES_PREY: "█",
    SPECIES_PREDATOR: "█",
}

SPECIES_COLOR: dict[int, str] = {
    SPECIES_EMPTY: "black",
    SPECIES_PLANT: "green",
    SPECIES_PREY: "dodger_blue",
    SPECIES_PREDATOR: "red",
}


class GridWidget(Static):
    """Renders the 50×50 species grid using Rich markup.

    Each cell displays the highest-trophic species present.
    Uses block characters with species-specific colors.

    Refs: EVO-002 §4.3
    """

    DEFAULT_CSS = """
    GridWidget {
        width: 100%;
        height: auto;
        text-style: bold;
    }
    """

    def update_grid(self, payload: RenderPayload) -> None:
        """Update the grid display from a RenderPayload.

        Args:
            payload: Current simulation snapshot.

        Refs: EVO-002 §4.3
        """
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
