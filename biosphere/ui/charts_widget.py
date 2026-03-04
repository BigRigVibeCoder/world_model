"""Charts widget for TUI — population bar charts.

Refs: EVO-002 §4.3, BLU-001 §7.5
"""

from __future__ import annotations

from textual.widgets import Static

from biosphere.ui.payload import RenderPayload

# ── Bar Chart Constants ───────────────────────────────────────────────────────

BAR_WIDTH: int = 40
BAR_CHAR: str = "█"
EMPTY_CHAR: str = "░"


class ChartsWidget(Static):
    """Renders population bar charts for plant/prey/predator.

    Shows horizontal bars with counts and color coding.
    Also displays environment stats (health, energy, weather).

    Refs: EVO-002 §4.3
    """

    DEFAULT_CSS = """
    ChartsWidget {
        width: 100%;
        height: auto;
        padding: 1;
    }
    """

    def update_charts(self, payload: RenderPayload) -> None:
        """Update chart display from a RenderPayload.

        Args:
            payload: Current simulation snapshot.

        Refs: EVO-002 §4.3
        """
        total = max(payload.n_plants + payload.n_prey + payload.n_predators, 1)

        lines: list[str] = [
            f"[bold]Tick: {payload.tick}[/]",
            "",
            self._bar_line("🌱 Plants", payload.n_plants, total, "green"),
            self._bar_line("🐇 Prey", payload.n_prey, total, "dodger_blue"),
            self._bar_line("🐺 Predators", payload.n_predators, total, "red"),
            "",
            "[bold]Stats[/]",
            f"  Health:  {payload.mean_health:.2f}",
            f"  Energy:  {payload.mean_energy:.2f}",
            f"  Rain:    {payload.mean_precipitation:.2f}",
            f"  Sun:     {payload.mean_sunlight:.2f}",
        ]

        self.update("\n".join(lines))

    @staticmethod
    def _bar_line(label: str, count: int, total: int, color: str) -> str:
        """Render a single bar line.

        Args:
            label: Species label with emoji.
            count: Population count.
            total: Total population for scaling.
            color: Rich color name.

        Returns:
            Formatted bar string.
        """
        ratio = count / total if total > 0 else 0.0
        filled = int(ratio * BAR_WIDTH)
        empty = BAR_WIDTH - filled
        bar = f"[{color}]{BAR_CHAR * filled}[/]{EMPTY_CHAR * empty}"
        return f"  {label:16s} {bar} {count:>5d}"
