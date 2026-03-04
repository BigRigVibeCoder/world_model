"""Contract tests for the RL Codec static API.

GOV-002 §9: Every inter-component API must have contract tests.
Verifies that the static methods build_observation(), compute_action_masks(),
and decode_action() produce outputs conforming to their documented contracts.

These are NOT integration tests (no multi-step loops) — they verify the
schema contracts between producer (engine state) and consumer (RL agent).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from biosphere.core.state import (
    GRID_H,
    GRID_W,
    MAX_PER_CELL,
    Intervention,
    InterventionType,
)
from biosphere.rl.environment import (
    ACTION_TYPE_SIZE,
    INTENSITY_MAP,
    INTENSITY_SIZE,
    MASK_SIZE,
    REGION_SIZE,
    SPECIES_DIM_SIZE,
    BiosphereEnv,
)
from biosphere.rl.reward import ENTROPY_WINDOW


@pytest.mark.contract
class TestBuildObservationContract:
    """Contract: build_observation() output matches observation_space.

    Refs: BLU-002 §3.3, §3.5, GOV-002 §9
    """

    def test_output_keys_match_space(self, biosphere_env: Any) -> None:
        """Output dict has exactly the keys defined in observation_space.

        Refs: BLU-002 §3.3, GOV-002 §9
        """
        state = biosphere_env._engine.get_state()
        history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        obs = BiosphereEnv.build_observation(state, history)

        assert set(obs.keys()) == {
            "grid_summary", "population_stats",
            "entropy_history", "weather_state",
        }
        assert biosphere_env.observation_space.contains(obs)

    def test_grid_summary_contract(self, biosphere_env: Any) -> None:
        """grid_summary: (50,50,4) uint8, per-species counts per cell.

        Refs: BLU-002 §3.3, GOV-002 §9
        """
        state = biosphere_env._engine.get_state()
        history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        obs = BiosphereEnv.build_observation(state, history)

        gs = obs["grid_summary"]
        assert gs.shape == (GRID_H, GRID_W, 4)
        assert gs.dtype == np.uint8
        # Each channel count ≤ MAX_PER_CELL
        assert gs.max() <= MAX_PER_CELL

    def test_population_stats_contract(self, biosphere_env: Any) -> None:
        """population_stats: (3,3) float32, [species][health, energy, count].

        Refs: BLU-002 §3.3, GOV-002 §9
        """
        state = biosphere_env._engine.get_state()
        history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        obs = BiosphereEnv.build_observation(state, history)

        ps = obs["population_stats"]
        assert ps.shape == (3, 3)
        assert ps.dtype == np.float32
        # Counts are non-negative
        assert (ps[:, 2] >= 0).all()

    def test_weather_state_contract(self, biosphere_env: Any) -> None:
        """weather_state: (4,) float32, [mean_precip, mean_sun, std_precip, std_sun].

        Refs: BLU-002 §3.3, GOV-002 §9
        """
        state = biosphere_env._engine.get_state()
        history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        obs = BiosphereEnv.build_observation(state, history)

        ws = obs["weather_state"]
        assert ws.shape == (4,)
        assert ws.dtype == np.float32
        assert np.all(np.isfinite(ws))


@pytest.mark.contract
class TestComputeActionMasksContract:
    """Contract: compute_action_masks() output matches documented spec.

    Refs: BLU-002 §3.2, §3.5, GOV-002 §9
    """

    def test_mask_shape_and_dtype(self, biosphere_env: Any) -> None:
        """Mask is flat (37,) bool.

        Refs: BLU-002 §3.2, GOV-002 §9
        """
        state = biosphere_env._engine.get_state()
        mask = BiosphereEnv.compute_action_masks(state)

        assert mask.shape == (MASK_SIZE,)
        assert mask.dtype == bool

    def test_mask_layout_segments(self, biosphere_env: Any) -> None:
        """Mask segments: type(4) + intensity(5) + species(3) + region(25) = 37.

        Refs: BLU-002 §3.2, GOV-002 §9
        """
        state = biosphere_env._engine.get_state()
        mask = BiosphereEnv.compute_action_masks(state)

        assert len(mask) == ACTION_TYPE_SIZE + INTENSITY_SIZE + SPECIES_DIM_SIZE + REGION_SIZE
        # Type and intensity always True
        assert mask[:ACTION_TYPE_SIZE].all()
        assert mask[ACTION_TYPE_SIZE:ACTION_TYPE_SIZE + INTENSITY_SIZE].all()


@pytest.mark.contract
class TestDecodeActionContract:
    """Contract: decode_action() returns valid Intervention for all valid inputs.

    Refs: BLU-002 §3.1, §3.5, GOV-002 §9
    """

    def test_output_is_intervention(self) -> None:
        """decode_action returns Intervention instance.

        Refs: BLU-002 §3.1, GOV-002 §9
        """
        action = np.array([0, 0, 0, 0])
        iv = BiosphereEnv.decode_action(action)

        assert isinstance(iv, Intervention)
        assert hasattr(iv, "type")
        assert hasattr(iv, "region_row")
        assert hasattr(iv, "intensity")

    def test_all_valid_actions_decode(self) -> None:
        """Every valid action combination produces a valid Intervention.

        Refs: BLU-002 §3.1, GOV-002 §9
        """
        for t in range(ACTION_TYPE_SIZE):
            for i in range(INTENSITY_SIZE):
                for s in range(SPECIES_DIM_SIZE):
                    for r in range(REGION_SIZE):
                        action = np.array([t, i, s, r])
                        iv = BiosphereEnv.decode_action(action)
                        assert isinstance(iv, Intervention)
                        assert iv.type == InterventionType(t)
                        assert iv.intensity == INTENSITY_MAP[i]

    @given(
        t=st.integers(min_value=0, max_value=ACTION_TYPE_SIZE - 1),
        i=st.integers(min_value=0, max_value=INTENSITY_SIZE - 1),
        s=st.integers(min_value=0, max_value=SPECIES_DIM_SIZE - 1),
        r=st.integers(min_value=0, max_value=REGION_SIZE - 1),
    )
    @settings(max_examples=50, deadline=5000)
    @pytest.mark.property
    def test_property_all_valid_actions(
        self, t: int, i: int, s: int, r: int,
    ) -> None:
        """Hypothesis: all valid action combos decode without error.

        Refs: BLU-002 §3.1, GOV-002 §5, §9
        """
        action = np.array([t, i, s, r])
        iv = BiosphereEnv.decode_action(action)
        assert isinstance(iv, Intervention)
        assert 0.0 <= iv.intensity <= 1.0
