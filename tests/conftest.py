"""Shared test fixtures and configuration.

GOV-002 §23: Deterministic seeds, isolation, shared fixtures.
GOV-002 §6: Every test starts clean, runs in isolation.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from biosphere.core.simulation import SimulationEngine
from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    SPECIES_PLANT,
)

# ── GOV-002 §23: Deterministic Seeds ─────────────────────────────────────────

DETERMINISTIC_SEED: int = 42


@pytest.fixture
def rng() -> np.random.Generator:
    """Deterministic NumPy RNG for reproducible tests.

    Refs: GOV-002 §23
    """
    return np.random.default_rng(DETERMINISTIC_SEED)


# ── Parameter Factories ──────────────────────────────────────────────────────


def make_params(**overrides: Any) -> SimpleNamespace:
    """Create valid SimulationParams with optional overrides.

    Refs: BLU-002 §2.4
    """
    defaults: dict[str, Any] = {
        "growth_rate": 0.1,
        "reproduction_threshold": 0.6,
        "max_age_prey": 500,
        "max_age_predator": 300,
        "metabolic_rate": 0.02,
        "weather_sigma": 2.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def default_params() -> SimpleNamespace:
    """Default valid SimulationParams fixture.

    Refs: BLU-002 §2.4
    """
    return make_params()


@pytest.fixture
def engine(default_params: SimpleNamespace) -> SimulationEngine:
    """Fresh SimulationEngine with default parameters.

    Refs: EVO-001, BLU-002 §2.2
    """
    return SimulationEngine(default_params)


@pytest.fixture
def stepped_engine(engine: SimulationEngine) -> SimulationEngine:
    """Engine that has already executed one step (has previous state).

    Refs: BLU-002 §2.2
    """
    engine.step()
    return engine


# ── Sprint 2: RL Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def biosphere_env() -> Any:
    """Fresh BiosphereEnv with default config.

    Refs: EVO-002, BLU-002 §3
    """
    from biosphere.rl.environment import BiosphereEnv

    env = BiosphereEnv()
    env.reset(seed=DETERMINISTIC_SEED)
    return env


@pytest.fixture
def training_config_path() -> Path:
    """Path to training YAML config.

    Refs: EVO-002 §4.2
    """
    return Path("config/training.yaml")


# ── Sprint 2: UI Fixtures ────────────────────────────────────────────────────


def make_payload(
    tick: int = 0,
    n_plants: int = 100,
    n_prey: int = 50,
    n_pred: int = 10,
) -> Any:
    """Create a RenderPayload from specified population counts.

    Refs: EVO-002 §4.3
    """
    from biosphere.ui.payload import RenderPayload

    sg = np.zeros((GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8)
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
        entropy=0.8,
        reward=0.5,
        paused=False,
    )

