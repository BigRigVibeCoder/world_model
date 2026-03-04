"""Main TUI application for Biosphere.

Refs: EVO-002 §4.3, BLU-001 §7.5
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

from biosphere.core.simulation import SimulationEngine
from biosphere.core.state import (
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
)
from biosphere.infrastructure.config import SimulationConfig
from biosphere.ui.charts_widget import ChartsWidget
from biosphere.ui.grid_widget import GridWidget
from biosphere.ui.payload import RenderPayload

# ── Constants ─────────────────────────────────────────────────────────────────

TARGET_FPS: float = 30.0
TICK_INTERVAL: float = 1.0 / TARGET_FPS


class BiosphereApp(App):  # type: ignore[type-arg]
    """Textual TUI application for Biosphere simulation.

    Displays a 50×50 species grid alongside population bar charts.
    Simulation runs at ~30 FPS via Textual's timer system.

    Refs: EVO-002 §4.3
    """

    CSS = """
    #main {
        layout: horizontal;
    }
    #grid-panel {
        width: 2fr;
        height: 100%;
        border: solid green;
    }
    #stats-panel {
        width: 1fr;
        height: 100%;
        border: solid cyan;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "toggle_pause", "Pause/Resume"),
    ]

    def __init__(
        self,
        config: SimulationConfig | None = None,
    ) -> None:
        """Initialize BiosphereApp.

        Args:
            config: Optional SimulationConfig for the engine.

        Refs: EVO-002 §4.3
        """
        super().__init__()
        self._config = config or SimulationConfig()
        self._engine = SimulationEngine(self._config)
        self._paused = False
        self._grid_widget = GridWidget(id="grid")
        self._charts_widget = ChartsWidget(id="charts")

    def compose(self) -> ComposeResult:
        """Compose the TUI layout.

        Refs: EVO-002 §4.3
        """
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="grid-panel"):
                yield self._grid_widget
            with Vertical(id="stats-panel"):
                yield self._charts_widget
        yield Footer()

    def on_mount(self) -> None:
        """Start the simulation timer on mount.

        Refs: EVO-002 §4.3
        """
        self.set_interval(TICK_INTERVAL, self._tick)
        # Initial render
        self._render_state()

    def _tick(self) -> None:
        """Advance simulation one step and update display."""
        if self._paused:
            return
        self._engine.step()
        self._render_state()

    def _render_state(self) -> None:
        """Build RenderPayload from current state and update widgets."""
        state = self._engine.get_state()
        sg = state["species_grid"]
        oa = state["organism_attrs"]
        weather = state["weather"]

        alive = sg != SPECIES_EMPTY
        mean_health = float(oa[:, :, :, 0][alive].mean()) if alive.any() else 0.0
        mean_energy = float(oa[:, :, :, 1][alive].mean()) if alive.any() else 0.0

        payload = RenderPayload(
            tick=self._engine.tick,
            species_grid=sg,
            n_plants=int((sg == SPECIES_PLANT).sum()),
            n_prey=int((sg == SPECIES_PREY).sum()),
            n_predators=int((sg == SPECIES_PREDATOR).sum()),
            mean_health=mean_health,
            mean_energy=mean_energy,
            mean_precipitation=float(weather[:, :, 0].mean()),
            mean_sunlight=float(weather[:, :, 1].mean()),
        )

        self._grid_widget.update_grid(payload)
        self._charts_widget.update_charts(payload)

    def action_toggle_pause(self) -> None:
        """Toggle simulation pause state."""
        self._paused = not self._paused
