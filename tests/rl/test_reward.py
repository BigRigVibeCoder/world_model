"""Tests for biosphere.rl.reward — multi-objective reward function.

Refs: EVO-002 §4.1, BLU-002 §3.4
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §5: Hypothesis property tests for reward invariants.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
)
from biosphere.rl.reward import (
    ENTROPY_WINDOW,
    TERMINAL_PENALTY,
    compute_reward,
    shannon_entropy,
)


def _make_state(
    n_plants: int = 100,
    n_prey: int = 50,
    n_pred: int = 10,
) -> dict[str, np.ndarray]:
    """Create a minimal GridState with specified population counts."""
    sg = np.zeros((GRID_H, GRID_W, MAX_PER_CELL), dtype=np.uint8)
    oa = np.zeros((GRID_H, GRID_W, MAX_PER_CELL, 3), dtype=np.float32)

    # Place organisms sequentially
    placed = 0
    for r in range(GRID_H):
        for c in range(GRID_W):
            for s in range(MAX_PER_CELL):
                if placed < n_plants:
                    sg[r, c, s] = SPECIES_PLANT
                    oa[r, c, s] = [0.8, 0.5, 10.0]
                    placed += 1
                elif placed < n_plants + n_prey:
                    sg[r, c, s] = SPECIES_PREY
                    oa[r, c, s] = [0.7, 0.4, 5.0]
                    placed += 1
                elif placed < n_plants + n_prey + n_pred:
                    sg[r, c, s] = SPECIES_PREDATOR
                    oa[r, c, s] = [0.6, 0.3, 3.0]
                    placed += 1

    return {
        "terrain": np.zeros((GRID_H, GRID_W, 3), dtype=np.float32),
        "species_grid": sg,
        "organism_attrs": oa,
        "resources": np.full((GRID_H, GRID_W, 2), 0.5, dtype=np.float32),
        "weather": np.full((GRID_H, GRID_W, 2), 0.5, dtype=np.float32),
    }


@pytest.mark.unit
class TestShannonEntropy:
    """Shannon entropy calculation per BLU-002 §3.4."""

    def test_uniform_distribution_max_entropy(self) -> None:
        """Equal populations produce maximum entropy.

        Refs: BLU-002 §3.4
        """
        pops = np.array([100, 100, 100])
        h = shannon_entropy(pops)
        assert h > 0.0
        assert abs(h - np.log(3)) < 1e-6

    def test_single_species_zero_entropy(self) -> None:
        """Single species has zero entropy.

        Refs: BLU-002 §3.4
        """
        pops = np.array([100, 0, 0])
        h = shannon_entropy(pops)
        assert h == 0.0
        assert isinstance(h, float)

    def test_empty_population_zero_entropy(self) -> None:
        """Zero total population returns zero entropy.

        Refs: BLU-002 §3.4
        """
        pops = np.array([0, 0, 0])
        h = shannon_entropy(pops)
        assert h == 0.0
        assert isinstance(h, float)


@pytest.mark.unit
class TestComputeReward:
    """Multi-objective reward function per BLU-002 §3.4."""

    def test_terminal_on_extinction(self) -> None:
        """All prey + predator extinct triggers terminal penalty.

        Refs: BLU-002 §3.4
        """
        state = _make_state(n_plants=100, n_prey=0, n_pred=0)
        history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        reward, terminated = compute_reward(state, history, 0)
        assert terminated is True
        assert reward == TERMINAL_PENALTY

    def test_not_terminal_with_prey(self) -> None:
        """Prey alive → not terminated, positive reward.

        Refs: BLU-002 §3.4
        """
        state = _make_state(n_plants=100, n_prey=50, n_pred=10)
        history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        reward, terminated = compute_reward(state, history, 0)
        assert terminated is False
        assert reward > 0.0

    def test_higher_entropy_higher_reward(self) -> None:
        """More diverse populations produce higher reward.

        Refs: BLU-002 §3.4
        """
        history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)

        # Unbalanced: mostly plants
        state_low = _make_state(n_plants=200, n_prey=5, n_pred=1)
        reward_low, _ = compute_reward(state_low, history.copy(), 0)

        # Balanced
        state_high = _make_state(n_plants=100, n_prey=100, n_pred=100)
        reward_high, _ = compute_reward(state_high, history.copy(), 0)

        assert reward_high > reward_low


@pytest.mark.property
class TestRewardPropertyBased:
    """Hypothesis property tests for reward invariants.

    GOV-002 §5
    """

    @given(
        n_plants=st.integers(min_value=1, max_value=200),
        n_prey=st.integers(min_value=1, max_value=100),
        n_pred=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=20, deadline=10000)
    def test_reward_finite_for_alive_populations(
        self, n_plants: int, n_prey: int, n_pred: int,
    ) -> None:
        """Reward is always finite when there are alive organisms.

        Refs: BLU-002 §3.4, GOV-002 §5
        """
        state = _make_state(n_plants=n_plants, n_prey=n_prey, n_pred=n_pred)
        history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        reward, terminated = compute_reward(state, history, 0)
        assert np.isfinite(reward)
        assert terminated is False
