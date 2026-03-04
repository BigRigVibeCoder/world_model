"""Biosphere demo — headless simulation with live population output.

Usage:
    source .venv/bin/activate
    PYTHONPATH=. python scripts/demo.py

Runs 200 ticks of the ecosystem and prints population dynamics.
"""

from __future__ import annotations

from biosphere.core.simulation import SimulationEngine
from biosphere.core.state import SPECIES_PLANT, SPECIES_PREDATOR, SPECIES_PREY
from biosphere.infrastructure.config import SimulationConfig


def main() -> None:
    """Run a headless demo of the biosphere simulation."""
    config = SimulationConfig()
    engine = SimulationEngine(config)

    print("🌿 Biosphere Ecological Balancer — Demo")
    print("=" * 55)
    print(f"{'Tick':>5} | {'Plants':>7} | {'Prey':>5} | {'Predators':>9} | {'Total':>6}")
    print("-" * 55)

    for i in range(200):
        state = engine.step()
        sg = state["species_grid"]
        n_plant = int((sg == SPECIES_PLANT).sum())
        n_prey = int((sg == SPECIES_PREY).sum())
        n_pred = int((sg == SPECIES_PREDATOR).sum())
        total = n_plant + n_prey + n_pred

        if i % 5 == 0 or i < 10:
            bar_p = "🌿" * min(n_plant // 50, 20)
            bar_y = "🐰" * min(n_prey // 10, 15)
            bar_d = "🐺" * min(n_pred // 5, 10)
            print(
                f"{i + 1:>5} | {n_plant:>7} | {n_prey:>5} | {n_pred:>9} | "
                f"{total:>6}  {bar_p}{bar_y}{bar_d}",
            )

    print("-" * 55)
    print("✅ Simulation complete — 200 ticks processed")
    print()

    # Final ecosystem health
    sg = engine.get_state()["species_grid"]
    n_plant = int((sg == SPECIES_PLANT).sum())
    n_prey = int((sg == SPECIES_PREY).sum())
    n_pred = int((sg == SPECIES_PREDATOR).sum())

    if n_prey > 0 and n_pred > 0:
        print("🎉 All three species survived — ecosystem is healthy!")
    elif n_prey > 0 or n_pred > 0:
        print("⚠️  One species went extinct — ecosystem is degraded")
    else:
        print("💀 Total extinction — the ecosystem collapsed")


if __name__ == "__main__":
    main()
