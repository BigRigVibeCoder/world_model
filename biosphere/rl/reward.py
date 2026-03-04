"""Multi-objective reward function for BiosphereEnv.

Refs: BLU-002 §3.4
Components:
  - Biodiversity (Shannon entropy of species populations) — weight 1.0
  - Stability (negative variance of entropy over window) — weight 0.5
  - Population health (mean health of alive organisms) — weight 0.3
  - Terminal penalty (all non-plant species extinct) — -10.0
"""

from __future__ import annotations

import numpy as np

from biosphere.core.state import (
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
    GridState,
)

# ── Reward Weights (BLU-002 §3.4) ────────────────────────────────────────────

W_BIODIVERSITY: float = 1.0
W_STABILITY: float = 0.5
W_HEALTH: float = 0.3
TERMINAL_PENALTY: float = -10.0
ENTROPY_WINDOW: int = 100


def shannon_entropy(populations: np.ndarray) -> float:
    """Compute Shannon entropy of species population counts.

    Args:
        populations: Array of population counts (e.g., [n_plant, n_prey, n_pred]).

    Returns:
        Shannon entropy H = -Σ(p_i * log(p_i)) where p_i = count_i / total.
        Returns 0.0 if total population is 0.

    Refs: BLU-002 §3.4
    """
    total = populations.sum()
    if total == 0:
        return 0.0
    probs = populations / total
    # Filter out zero probabilities to avoid log(0)
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log(probs)))


def compute_reward(
    state: GridState,
    entropy_history: np.ndarray,
    current_step: int,
) -> tuple[float, bool]:
    """Compute multi-objective reward and terminal flag.

    Args:
        state: Current GridState from the simulation.
        entropy_history: Rolling window array of past entropy values, shape (100,).
        current_step: Current timestep (used to determine valid window).

    Returns:
        Tuple of (reward, terminated).
        terminated=True if all prey and predator are extinct.

    Refs: BLU-002 §3.4
    """
    sg = state["species_grid"]
    oa = state["organism_attrs"]

    # Population counts
    n_plant = int((sg == SPECIES_PLANT).sum())
    n_prey = int((sg == SPECIES_PREY).sum())
    n_pred = int((sg == SPECIES_PREDATOR).sum())
    populations = np.array([n_plant, n_prey, n_pred], dtype=np.float64)

    # Terminal condition: all non-plant species extinct
    terminated = n_prey == 0 and n_pred == 0

    if terminated:
        return TERMINAL_PENALTY, True

    # Component 1: Biodiversity (Shannon entropy)
    entropy = shannon_entropy(populations)

    # Update entropy history
    idx = current_step % ENTROPY_WINDOW
    entropy_history[idx] = entropy

    # Component 2: Stability (negative variance over window)
    window_size = min(current_step + 1, ENTROPY_WINDOW)
    if window_size > 1:
        valid_entries = entropy_history[:window_size]
        stability = -float(np.var(valid_entries))
    else:
        stability = 0.0

    # Component 3: Population health (mean health of alive organisms)
    alive_mask = sg != SPECIES_EMPTY
    if alive_mask.any():
        health_vals = oa[:, :, :, 0][alive_mask]
        mean_health = float(np.mean(health_vals))
    else:
        mean_health = 0.0

    reward = (
        W_BIODIVERSITY * entropy
        + W_STABILITY * stability
        + W_HEALTH * mean_health
    )

    return reward, False
