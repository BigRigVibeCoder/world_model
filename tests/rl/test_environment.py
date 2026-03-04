"""Tests for biosphere.rl.environment — BiosphereEnv Gymnasium environment.

Refs: EVO-002 §4.1, BLU-002 §3
GOV-002 §4: Assertion density ≥2 per test.
GOV-002 §19: Refs traceability in every docstring.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from biosphere.core.state import (
    SPECIES_PREDATOR,
    SPECIES_PREY,
    InterventionType,
)
from biosphere.rl.environment import (
    ACTION_TYPE_SIZE,
    INTENSITY_MAP,
    INTENSITY_SIZE,
    MASK_SIZE,
    REGION_MAP,
    SPECIES_DIM_SIZE,
    ActionDecodingError,
    BiosphereEnv,
)


@pytest.mark.unit
class TestActionSpace:
    """Action space shape and bounds per BLU-002 §3.1."""

    def test_action_space_shape(self) -> None:
        """MultiDiscrete([4, 5, 3, 25]) per BLU-002 §3.1.

        Refs: BLU-002 §3.1
        """
        env = BiosphereEnv()
        nvec = env.action_space.nvec
        assert list(nvec) == [4, 5, 3, 25]
        assert len(nvec) == 4

    def test_action_space_sample(self) -> None:
        """Sampled action has correct shape and valid values.

        Refs: BLU-002 §3.1
        """
        env = BiosphereEnv()
        action = env.action_space.sample()
        assert action.shape == (4,)
        assert 0 <= action[0] < ACTION_TYPE_SIZE


@pytest.mark.unit
class TestObservationSpace:
    """Observation space structure per BLU-002 §3.3."""

    def test_observation_keys(self) -> None:
        """Observation has all 4 required keys.

        Refs: BLU-002 §3.3
        """
        env = BiosphereEnv()
        obs, info = env.reset()
        assert set(obs.keys()) == {
            "grid_summary", "population_stats",
            "entropy_history", "weather_state",
        }
        assert isinstance(info, dict)

    def test_grid_summary_shape(self) -> None:
        """grid_summary is (50, 50, 4) uint8.

        Refs: BLU-002 §3.3
        """
        env = BiosphereEnv()
        obs, _ = env.reset()
        assert obs["grid_summary"].shape == (50, 50, 4)
        assert obs["grid_summary"].dtype == np.uint8

    def test_population_stats_shape(self) -> None:
        """population_stats is (3, 3) float32.

        Refs: BLU-002 §3.3
        """
        env = BiosphereEnv()
        obs, _ = env.reset()
        assert obs["population_stats"].shape == (3, 3)
        assert obs["population_stats"].dtype == np.float32

    def test_entropy_history_shape(self) -> None:
        """entropy_history is (100,) float32.

        Refs: BLU-002 §3.3
        """
        env = BiosphereEnv()
        obs, _ = env.reset()
        assert obs["entropy_history"].shape == (100,)
        assert obs["entropy_history"].dtype == np.float32


@pytest.mark.unit
class TestActionMasks:
    """Action mask logic per BLU-002 §3.2."""

    def test_mask_shape_and_dtype(self) -> None:
        """Action mask is flat (37,) bool array.

        Refs: BLU-002 §3.2
        """
        env = BiosphereEnv()
        env.reset()
        mask = env.action_masks()
        assert mask.shape == (MASK_SIZE,)
        assert mask.dtype == bool

    def test_unused_species_always_masked(self) -> None:
        """Species index 2 is always False (unused slot).

        Refs: BLU-002 §3.2
        """
        env = BiosphereEnv()
        env.reset()
        mask = env.action_masks()
        species_offset = ACTION_TYPE_SIZE + INTENSITY_SIZE
        assert mask[species_offset + 2] is np.bool_(False)
        assert mask[species_offset + 0] is np.bool_(True)  # prey exists at start

    def test_type_intensity_region_always_true(self) -> None:
        """Type, intensity, and region dimensions are always unmasked.

        Refs: BLU-002 §3.2
        """
        env = BiosphereEnv()
        env.reset()
        mask = env.action_masks()
        # First 4 (type) + next 5 (intensity) = all True
        assert mask[:ACTION_TYPE_SIZE].all()
        assert mask[ACTION_TYPE_SIZE:ACTION_TYPE_SIZE + INTENSITY_SIZE].all()
        # Last 25 (region) = all True
        region_offset = ACTION_TYPE_SIZE + INTENSITY_SIZE + SPECIES_DIM_SIZE
        assert mask[region_offset:].all()


@pytest.mark.unit
class TestDecodeAction:
    """Action decoding per BLU-002 §3.1, §3.5."""

    def test_no_op_decode(self) -> None:
        """Action [0, 0, 0, 0] decodes to NO_OP intervention.

        Refs: BLU-002 §3.1
        """
        action = np.array([0, 0, 0, 0])
        iv = BiosphereEnv.decode_action(action)
        assert iv.type == InterventionType.NO_OP
        assert iv.intensity == 0.0

    def test_seed_plants_decode(self) -> None:
        """Action [1, 4, 0, 12] decodes to SEED_PLANTS at intensity 1.0 in region 12.

        Refs: BLU-002 §3.1
        """
        action = np.array([1, 4, 0, 12])
        iv = BiosphereEnv.decode_action(action)
        assert iv.type == InterventionType.SEED_PLANTS
        assert iv.intensity == 1.0
        assert iv.region_row == REGION_MAP[12][0]
        assert iv.region_col == REGION_MAP[12][1]

    def test_cull_prey_decode(self) -> None:
        """Action [3, 2, 0, 0] decodes to CULL_SPECIES targeting prey at intensity 0.5.

        Refs: BLU-002 §3.1
        """
        action = np.array([3, 2, 0, 0])
        iv = BiosphereEnv.decode_action(action)
        assert iv.type == InterventionType.CULL_SPECIES
        assert iv.target_species == SPECIES_PREY
        assert iv.intensity == 0.5

    def test_cull_predator_decode(self) -> None:
        """Action [3, 3, 1, 5] decodes to CULL_SPECIES targeting predator.

        Refs: BLU-002 §3.1
        """
        action = np.array([3, 3, 1, 5])
        iv = BiosphereEnv.decode_action(action)
        assert iv.type == InterventionType.CULL_SPECIES
        assert iv.target_species == SPECIES_PREDATOR

    def test_invalid_action_length_raises(self) -> None:
        """Wrong action length raises ActionDecodingError.

        Refs: BLU-002 §4
        """
        with pytest.raises(ActionDecodingError):
            BiosphereEnv.decode_action(np.array([0, 0]))
        with pytest.raises(ActionDecodingError):
            BiosphereEnv.decode_action(np.array([0, 0, 0, 0, 0]))

    def test_action_round_trip(self) -> None:
        """Encode→decode produces valid Intervention for all type×intensity combos.

        Refs: BLU-002 §3.5
        """
        for t in range(ACTION_TYPE_SIZE):
            for i in range(INTENSITY_SIZE):
                action = np.array([t, i, 0, 0])
                iv = BiosphereEnv.decode_action(action)
                assert iv.type == InterventionType(t)
                assert iv.intensity == INTENSITY_MAP[i]


@pytest.mark.unit
class TestStepAndReset:
    """Gym step/reset lifecycle per BLU-002 §3."""

    def test_reset_returns_valid_obs(self) -> None:
        """reset() returns observation matching observation_space.

        Refs: BLU-002 §3
        """
        env = BiosphereEnv()
        obs, info = env.reset()
        assert env.observation_space.contains(obs)
        assert "tick" in info

    def test_step_returns_five_tuple(self) -> None:
        """step() returns (obs, reward, terminated, truncated, info).

        Refs: BLU-002 §3
        """
        env = BiosphereEnv()
        env.reset()
        action = env.action_space.sample()
        result = env.step(action)
        assert len(result) == 5
        obs, reward, terminated, truncated, info = result
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)

    def test_10_steps_no_crash(self) -> None:
        """10 random steps complete without errors.

        Refs: EVO-002 §4.1
        """
        env = BiosphereEnv()
        env.reset()
        for _ in range(10):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                obs, info = env.reset()
        assert info["tick"] >= 0
        assert env.observation_space.contains(obs)

    def test_render_ansi(self) -> None:
        """ANSI render mode produces string output.

        Refs: EVO-002 §4.3
        """
        env = BiosphereEnv(render_mode="ansi")
        env.reset()
        rendered = env.render()
        assert isinstance(rendered, str)
        assert len(rendered) > 0


@pytest.mark.integration
class TestGymChecker:
    """Gymnasium env_checker smoke test per EVO-002 §4.1."""

    def test_check_env_passes(self) -> None:
        """gymnasium.utils.env_checker.check_env() passes.

        Refs: EVO-002 §4.1, BLU-002 §3
        """
        from gymnasium.utils.env_checker import check_env

        env = BiosphereEnv()
        # check_env will raise or warn on issues
        check_env(env.unwrapped, skip_render_check=True)
        assert True  # If we reach here, check_env passed


@pytest.mark.property
class TestEnvPropertyBased:
    """Hypothesis property tests for environment invariants.

    GOV-002 §5: Property-based tests for all validation/processing functions.
    """

    @given(seed=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=10, deadline=30000)
    def test_mask_always_valid_shape(self, seed: int) -> None:
        """Action mask is always (37,) bool regardless of seed.

        Refs: BLU-002 §3.2, GOV-002 §5
        """
        env = BiosphereEnv()
        env.reset(seed=seed)
        mask = env.action_masks()
        assert mask.shape == (MASK_SIZE,)
        assert mask.dtype == bool

    @given(seed=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=10, deadline=30000)
    def test_obs_always_in_space(self, seed: int) -> None:
        """Observation is always within observation_space bounds.

        Refs: BLU-002 §3.3, GOV-002 §5
        """
        env = BiosphereEnv()
        obs, _ = env.reset(seed=seed)
        assert env.observation_space.contains(obs)
        # Step once
        action = env.action_space.sample()
        obs, _, _, _, _ = env.step(action)
        assert env.observation_space.contains(obs)

    @given(seed=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=10, deadline=30000)
    def test_unused_species_always_masked_property(self, seed: int) -> None:
        """Species slot 2 is always masked (unused) regardless of state.

        Refs: BLU-002 §3.2, GOV-002 §5
        """
        env = BiosphereEnv()
        env.reset(seed=seed)
        # Run a few steps
        for _ in range(5):
            mask = env.action_masks()
            species_offset = ACTION_TYPE_SIZE + INTENSITY_SIZE
            assert mask[species_offset + 2] is np.bool_(False)
            env.step(env.action_space.sample())

    @given(seed=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=10, deadline=30000)
    def test_reward_always_finite(self, seed: int) -> None:
        """Reward is always finite after any valid step.

        Refs: BLU-002 §3.4, GOV-002 §5
        """
        env = BiosphereEnv()
        env.reset(seed=seed)
        for _ in range(10):
            action = env.action_space.sample()
            _, reward, terminated, _, _ = env.step(action)
            assert np.isfinite(reward)
            if terminated:
                break
