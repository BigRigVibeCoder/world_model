"""Render payload for TUI dashboard.

Refs: EVO-002 §4.3, BLU-002 §1
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RenderPayload:
    """Snapshot of simulation state for UI rendering.

    Carries pre-computed data to the UI layer so widgets don't
    need to import or understand core state internals.

    Refs: EVO-002 §4.3
    """

    tick: int
    species_grid: np.ndarray
    n_plants: int
    n_prey: int
    n_predators: int
    mean_health: float
    mean_energy: float
    mean_precipitation: float
    mean_sunlight: float
    entropy: float
    reward: float
    paused: bool
