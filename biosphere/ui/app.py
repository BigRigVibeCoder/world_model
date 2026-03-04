"""Main TUI application for Biosphere.

Simulation dashboard with colored grid, population statistics,
and system metrics. Designed to look like a real-time ecological
simulation monitor.

Refs: EVO-002 §4.3, BLU-001 §7.5
"""

from __future__ import annotations

import numpy as np
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from biosphere.core.simulation import SimulationEngine
from biosphere.core.state import (
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
)
from biosphere.infrastructure.config import SimulationConfig
from biosphere.rl.reward import shannon_entropy
from biosphere.ui.charts_widget import ChartsWidget
from biosphere.ui.grid_widget import GridWidget
from biosphere.ui.payload import RenderPayload

# ── Constants ─────────────────────────────────────────────────────────────────

TARGET_FPS: float = 10.0
TICK_INTERVAL: float = 1.0 / TARGET_FPS


class BiosphereApp(App):  # type: ignore[type-arg]
    """Textual TUI for Biosphere ecological simulation.

    Displays a 50×50 species grid alongside population bar charts
    and real-time system metrics.

    Refs: EVO-002 §4.3
    """

    TITLE = "BIOSphere Ecological Balancer"
    SUB_TITLE = "Real-Time Ecosystem Simulation"

    CSS = """
    Screen {
        background: #0a0a0a;
    }
    Header {
        background: #111111;
        color: #00ccff;
        text-style: bold;
    }
    Footer {
        background: #111111;
        color: #888888;
    }
    #main {
        layout: horizontal;
        height: 1fr;
    }
    #grid-panel {
        width: 3fr;
        height: 100%;
        border: solid #00cc44;
        border-title-color: #00cc44;
        background: #0a0a0a;
    }
    #stats-panel {
        width: 2fr;
        height: 100%;
        border: solid #00ccff;
        border-title-color: #00ccff;
        background: #0a0a0a;
    }
    #legend {
        height: 1;
        dock: bottom;
        padding: 0 1;
        background: #111111;
        color: #888888;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "toggle_pause", "Pause/Resume"),
        ("r", "reset", "Reset"),
    ]

    def __init__(
        self,
        config: SimulationConfig | None = None,
    ) -> None:
        """Initialize BiosphereApp.

        Args:
            config: Optional SimulationConfig for the engine.
        """
        super().__init__()
        self._config = config or SimulationConfig()
        self._engine = SimulationEngine(self._config)
        self._paused = False
        self._grid_widget = GridWidget(id="grid")
        self._charts_widget = ChartsWidget(id="charts")
        self._legend = Static(
            "[#00cc44]● Plants[/]  "
            "[#ffcc00]● Prey[/]  "
            "[#ff3333]● Predators[/]  "
            "[#333333]· Empty[/]",
            id="legend",
        )
        self._entropy_history = np.zeros(100, dtype=np.float64)
        self._reward = 0.0

    def compose(self) -> ComposeResult:
        """Compose the TUI layout."""
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="grid-panel"):
                yield self._grid_widget
            with Vertical(id="stats-panel"):
                yield self._charts_widget
        yield self._legend
        yield Footer()

    def on_mount(self) -> None:
        """Start the simulation timer on mount."""
        grid_panel = self.query_one("#grid-panel")
        grid_panel.border_title = "Ecosystem Grid: 50x50"
        stats_panel = self.query_one("#stats-panel")
        stats_panel.border_title = "Dashboard"

        self.set_interval(TICK_INTERVAL, self._tick)
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

        n_plants = int((sg == SPECIES_PLANT).sum())
        n_prey = int((sg == SPECIES_PREY).sum())
        n_predators = int((sg == SPECIES_PREDATOR).sum())

        # Compute Shannon entropy
        populations = np.array([n_plants, n_prey, n_predators], dtype=np.float64)
        entropy = shannon_entropy(populations)

        # Track entropy history for reward stability component
        tick = self._engine.tick
        idx = tick % 100
        self._entropy_history[idx] = entropy

        # Simple reward approximation for display
        window_size = min(tick + 1, 100)
        if window_size > 1:
            stability = -float(np.var(self._entropy_history[:window_size]))
        else:
            stability = 0.0
        self._reward = entropy + 0.5 * stability + 0.3 * mean_health

        payload = RenderPayload(
            tick=tick,
            species_grid=sg,
            n_plants=n_plants,
            n_prey=n_prey,
            n_predators=n_predators,
            mean_health=mean_health,
            mean_energy=mean_energy,
            mean_precipitation=float(weather[:, :, 0].mean()),
            mean_sunlight=float(weather[:, :, 1].mean()),
            entropy=entropy,
            reward=self._reward,
            paused=self._paused,
        )

        self._grid_widget.update_grid(payload)
        self._charts_widget.update_charts(payload)

    def action_toggle_pause(self) -> None:
        """Toggle simulation pause state."""
        self._paused = not self._paused
        self._render_state()

    def action_reset(self) -> None:
        """Reset the simulation to initial state."""
        self._engine = SimulationEngine(self._config)
        self._entropy_history = np.zeros(100, dtype=np.float64)
        self._reward = 0.0
        self._paused = False
        self._render_state()
