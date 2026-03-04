"""Charts widget for TUI — population bars + system metrics.

Displays colored population bar charts and key simulation metrics
(tick, entropy, reward, sim state) in a panel layout.

Refs: EVO-002 §4.3, BLU-001 §7.5
"""

from __future__ import annotations

from textual.widgets import Static

from biosphere.ui.payload import RenderPayload

# ── Bar Chart Constants ───────────────────────────────────────────────────────

BAR_WIDTH: int = 30
BAR_CHAR: str = "█"
EMPTY_CHAR: str = "░"


class ChartsWidget(Static):
    """Renders population statistics and system metrics.

    Shows:
    - Population bar charts (green/yellow/red)
    - Total entities count
    - Biodiversity entropy
    - System state (tick, reward, running/paused)
    - Environment stats

    Refs: EVO-002 §4.3
    """

    DEFAULT_CSS = """
    ChartsWidget {
        width: 100%;
        height: 100%;
        padding: 1 2;
        background: #0a0a0a;
    }
    """

    def update_charts(self, payload: RenderPayload) -> None:
        """Update chart display from a RenderPayload."""
        total = payload.n_plants + payload.n_prey + payload.n_predators
        max_pop = max(payload.n_plants, payload.n_prey, payload.n_predators, 1)

        sim_state = "[#ff6666]Paused[/]" if payload.paused else "[#66ff66]Running[/]"

        lines: list[str] = [
            "[bold #00ccff]┌─ Population Statistics ─┐[/]",
            "",
            "[bold]POPULATION LEVELS[/]",
            "",
            self._bar_line("Plants", payload.n_plants, max_pop, "#00cc44"),
            "",
            self._bar_line("Prey", payload.n_prey, max_pop, "#ffcc00"),
            "",
            self._bar_line("Predators", payload.n_predators, max_pop, "#ff3333"),
            "",
            f"  Total Entities: [bold]{total}[/]",
            f"  H: [bold #00ccff]{payload.entropy:.2f}[/] (Diversity)",
            "",
            "[bold #00ccff]┌─ System State & Controls ─┐[/]",
            "",
            f"  Tick:      [bold]{payload.tick}[/]",
            f"  Entropy:   [bold #00ccff]{payload.entropy:.2f}[/]",
            f"  Reward:    [bold #ffcc00]{payload.reward:+.3f}[/]",
            f"  Sim:       {sim_state}",
            "",
            "[bold #00ccff]┌─ Environment ─┐[/]",
            "",
            f"  Health:    [bold]{payload.mean_health:.2f}[/]",
            f"  Energy:    [bold]{payload.mean_energy:.2f}[/]",
            f"  Rain:      [bold #4488ff]{payload.mean_precipitation:.2f}[/]",
            f"  Sun:       [bold #ffaa00]{payload.mean_sunlight:.2f}[/]",
        ]

        self.update("\n".join(lines))

    @staticmethod
    def _bar_line(label: str, count: int, max_pop: int, color: str) -> str:
        """Render a single population bar line.

        Args:
            label: Species label.
            count: Population count.
            max_pop: Maximum population (for scaling).
            color: Rich color code.

        Returns:
            Formatted bar string.
        """
        ratio = count / max_pop if max_pop > 0 else 0.0
        filled = int(ratio * BAR_WIDTH)
        empty = BAR_WIDTH - filled
        bar = f"[{color}]{BAR_CHAR * filled}[/][#333333]{EMPTY_CHAR * empty}[/]"
        return f"  {label:12s} {bar} [{color}]{count:>5d}[/]"
