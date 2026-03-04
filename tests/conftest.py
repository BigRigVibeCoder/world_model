"""Shared test fixtures and configuration.

GOV-002 §23: Deterministic seeds, isolation, shared fixtures.
GOV-002 §6: Every test starts clean, runs in isolation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from biosphere.core.simulation import SimulationEngine

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
