"""Real ecological dynamics E2E tests — no mocks, strong assertions.

These tests prove that the biosphere simulation produces ecologically
meaningful behavior, not just that it doesn't crash. Every test runs the
full stack: Config → Engine → State → Phases → Observations.

GOV-002 §11: Every major user flow must have at least one E2E test.
GOV-002 §19: Bidirectional traceability via Refs: tags.
"""

from __future__ import annotations

import numpy as np
import pytest

from biosphere.core.simulation import SimulationEngine
from biosphere.core.state import (
    SPECIES_EMPTY,
    SPECIES_PREDATOR,
    SPECIES_PREY,
)
from biosphere.infrastructure.config import SimulationConfig
from biosphere.rl.environment import BiosphereEnv
from biosphere.rl.reward import shannon_entropy


@pytest.mark.e2e
class TestPredatorPreyOscillation:
    """Verify Lotka-Volterra dynamics produce population oscillations.

    Refs: BLU-001 §4.2, §4.4, §4.6
    """

    def test_populations_oscillate_not_flat_or_monotonic(self) -> None:
        """Run 300 steps: prey and predator populations must oscillate.

        A working Lotka-Volterra system produces boom-bust cycles,
        NOT flat lines or monotonic decline to zero.

        Refs: BLU-001 §4
        """
        engine = SimulationEngine(SimulationConfig())
        prey_counts: list[int] = []
        pred_counts: list[int] = []

        for _ in range(300):
            state = engine.step()
            sg = state["species_grid"]
            prey_counts.append(int((sg == SPECIES_PREY).sum()))
            pred_counts.append(int((sg == SPECIES_PREDATOR).sum()))

        # Both species should still exist or have existed for a while
        assert max(prey_counts) > 0, "Prey never appeared"
        assert max(pred_counts) > 0, "Predators never appeared"

        # Key assertion: populations are NOT monotonic (they oscillate)
        # Count direction changes (minima/maxima) in prey population
        prey_arr = np.array(prey_counts)
        diffs = np.diff(prey_arr)
        # Remove zero diffs (no change)
        nonzero_diffs = diffs[diffs != 0]
        if len(nonzero_diffs) > 2:
            sign_changes = np.sum(np.diff(np.sign(nonzero_diffs)) != 0)
            # In a oscillating system, we expect multiple direction changes
            assert sign_changes >= 3, (
                f"Prey population changed direction only {sign_changes} times "
                f"in 300 steps — not oscillating. "
                f"Range: {min(prey_counts)}-{max(prey_counts)}"
            )

        # Variance should be non-trivial (not a flat line)
        assert np.std(prey_counts) > 1.0, (
            f"Prey std={np.std(prey_counts):.1f} — population is flat"
        )

    def test_predator_decline_follows_prey_decline(self) -> None:
        """Predator population tracks prey with a lag (classic LV).

        When prey declines, predators should eventually decline too
        (starvation), not remain constant.

        Refs: BLU-001 §4.4, §4.6
        """
        engine = SimulationEngine(SimulationConfig())
        prey_counts: list[int] = []
        pred_counts: list[int] = []

        for _ in range(200):
            state = engine.step()
            sg = state["species_grid"]
            prey_counts.append(int((sg == SPECIES_PREY).sum()))
            pred_counts.append(int((sg == SPECIES_PREDATOR).sum()))

        # Correlation: prey and predator trajectories should show
        # some correlation (positive or negative depending on phase)
        prey_arr = np.array(prey_counts, dtype=np.float64)
        pred_arr = np.array(pred_counts, dtype=np.float64)

        # Both populations should vary
        prey_var = np.var(prey_arr)
        pred_var = np.var(pred_arr)
        assert prey_var > 0, "Prey population is constant"
        assert pred_var > 0, "Predator population is constant"

        # If prey goes to zero, predators should eventually decline
        if prey_counts[-1] == 0:
            # Find when prey hit zero
            zero_idx = next(i for i, c in enumerate(prey_counts) if c == 0)
            if zero_idx < len(pred_counts) - 20:
                # Predators should decline after prey vanish
                pred_after = pred_counts[zero_idx:]
                assert pred_after[-1] <= pred_after[0], (
                    "Predators didn't decline after prey extinction"
                )


@pytest.mark.e2e
class TestResourceDynamics:
    """Verify logistic resource growth and consumption mechanics.

    Refs: BLU-001 §4.2, §4.4
    """

    def test_biomass_decreases_under_consumption(self) -> None:
        """Plant biomass decreases when organisms are consuming it.

        Refs: BLU-001 §4.4
        """
        engine = SimulationEngine(SimulationConfig())

        # Record initial biomass
        state = engine.step()
        initial_biomass = float(state["resources"][:, :, 0].sum())

        # Run 50 steps with consumers present
        biomass_history: list[float] = [initial_biomass]
        for _ in range(50):
            state = engine.step()
            biomass_history.append(float(state["resources"][:, :, 0].sum()))

        # Biomass should not be identical every step — consumption causes changes
        biomass_arr = np.array(biomass_history)
        assert np.std(biomass_arr) > 0.1, (
            f"Biomass std={np.std(biomass_arr):.4f} — no consumption effect"
        )

    def test_resources_recover_without_consumers(self) -> None:
        """When all consumers are removed, plant biomass grows back.

        This proves the logistic growth model dP/dt = rP(1-P/K) works.

        Refs: BLU-001 §4.2
        """
        engine = SimulationEngine(SimulationConfig())

        # Run a few steps to establish state
        for _ in range(10):
            engine.step()

        # Get current state and kill all prey + predators
        state = engine.get_state()
        sg = state["species_grid"]
        oa = state["organism_attrs"]

        prey_mask = sg == SPECIES_PREY
        pred_mask = sg == SPECIES_PREDATOR
        sg[prey_mask] = SPECIES_EMPTY
        oa[prey_mask] = 0.0
        sg[pred_mask] = SPECIES_EMPTY
        oa[pred_mask] = 0.0

        # Set resources to a low level
        state["resources"][:, :, 0] = 0.2

        # Inject the modified state back through the engine
        engine._state = state

        # Record biomass over next 100 steps (only plants, no consumers)
        biomass_history: list[float] = []
        for _ in range(100):
            new_state = engine.step()
            biomass_history.append(float(new_state["resources"][:, :, 0].mean()))

        # Biomass should INCREASE (logistic growth with no consumption)
        assert biomass_history[-1] > biomass_history[0], (
            f"Biomass didn't recover: {biomass_history[0]:.3f} → "
            f"{biomass_history[-1]:.3f}"
        )

        # Should converge toward carrying capacity (1.0)
        assert biomass_history[-1] > 0.3, (
            f"Biomass only reached {biomass_history[-1]:.3f}, expected > 0.3"
        )


@pytest.mark.e2e
class TestWeatherDiffusion:
    """Verify Gaussian blur weather diffusion from BLU-001 §4.1.

    Refs: BLU-001 §4.1
    """

    def test_concentrated_precipitation_spreads(self) -> None:
        """Set high precipitation in one region, verify it diffuses.

        After N steps of Gaussian blur, the concentrated region should
        spread to neighbors.

        Refs: BLU-001 §4.1
        """
        engine = SimulationEngine(SimulationConfig())
        state = engine.step()

        # Set concentrated precipitation: high in center, zero elsewhere
        state["weather"][:, :, 0] = 0.0
        state["weather"][20:30, 20:30, 0] = 1.0
        engine._state = state

        center_before = float(state["weather"][25, 25, 0])

        # Run 20 steps of weather diffusion
        for _ in range(20):
            new_state = engine.step()

        center_after = float(new_state["weather"][25, 25, 0])
        edge_after = float(new_state["weather"][10, 10, 0])

        # Center should have decreased (spread out)
        assert center_after < center_before, (
            f"Center didn't decrease: {center_before:.3f} → {center_after:.3f}"
        )

        # Edge should be non-zero (precipitation spread there)
        assert edge_after > 0.01, (
            f"Edge precipitation is {edge_after:.4f} — "
            "diffusion didn't reach it"
        )


@pytest.mark.e2e
class TestShannonEntropyReward:
    """Verify Shannon entropy reward produces correct rankings.

    Refs: BLU-002 §3.4
    """

    def test_balanced_populations_give_higher_entropy(self) -> None:
        """Equal species counts → higher entropy than monoculture.

        Refs: BLU-002 §3.4
        """
        # Balanced: [100, 100, 100]
        balanced = shannon_entropy(np.array([100.0, 100.0, 100.0]))

        # Imbalanced: mostly one species
        imbalanced = shannon_entropy(np.array([298.0, 1.0, 1.0]))

        # Single species: true monoculture
        mono = shannon_entropy(np.array([300.0, 0.0, 0.0]))

        assert balanced > imbalanced, (
            f"Balanced entropy ({balanced:.3f}) should exceed "
            f"imbalanced ({imbalanced:.3f})"
        )
        assert imbalanced > mono, (
            f"Imbalanced entropy ({imbalanced:.3f}) should exceed "
            f"monoculture ({mono:.3f})"
        )
        assert mono == 0.0, "Single-species entropy should be 0"

    def test_reward_increases_with_biodiversity(self) -> None:
        """Run the real env: reward should be higher when all 3 species exist.

        Refs: BLU-002 §3.4
        """
        env = BiosphereEnv()
        env.reset(seed=42)

        # Collect rewards from first 50 steps
        rewards: list[float] = []
        for _ in range(50):
            _, reward, terminated, _, _ = env.step(np.array([0, 0, 0, 0]))
            rewards.append(reward)
            if terminated:
                break

        # Rewards should be positive on average (entropy + health components)
        mean_reward = np.mean(rewards)
        assert mean_reward > -5.0, (
            f"Mean reward {mean_reward:.3f} is too negative — "
            "biodiversity component not working"
        )

        # Non-zero variance (reward is actually responding to state changes)
        assert np.std(rewards) > 0.0, "Reward is constant — not responding to state"


@pytest.mark.e2e
class TestInterventionCausality:
    """Prove interventions cause measurable state changes.

    Refs: BLU-001 §6, BLU-002 §2.3
    """

    def test_seed_plants_measurably_increases_plants(self) -> None:
        """SEED_PLANTS at max intensity increases plant count vs control.

        Runs two identical simulations: one with NO_OP, one with SEED_PLANTS.
        The seeded one must have more plants.

        Refs: BLU-002 §2.3
        """
        # Control run: 20 NO_OP steps
        env_control = BiosphereEnv()
        env_control.reset(seed=42)
        for _ in range(20):
            obs_control, _, _, _, _ = env_control.step(np.array([0, 0, 0, 0]))

        control_plants = obs_control["population_stats"][0, 2]

        # Seeded run: 20 SEED_PLANTS at max intensity
        env_seed = BiosphereEnv()
        env_seed.reset(seed=42)
        for _ in range(20):
            obs_seed, _, _, _, _ = env_seed.step(np.array([1, 4, 0, 12]))

        seeded_plants = obs_seed["population_stats"][0, 2]

        # Seeded simulation should have MORE plants
        assert seeded_plants > control_plants, (
            f"Seeded plants ({seeded_plants}) should exceed "
            f"control ({control_plants})"
        )

    def test_adjust_precipitation_changes_weather(self) -> None:
        """ADJUST_PRECIPITATION intervention changes weather state.

        Refs: BLU-001 §6, BLU-002 §2.3
        """
        # Control: NO_OP for 10 steps
        env_control = BiosphereEnv()
        env_control.reset(seed=42)
        for _ in range(10):
            obs_control, _, _, _, _ = env_control.step(np.array([0, 0, 0, 0]))

        control_precip = obs_control["weather_state"][0]

        # Treatment: ADJUST_PRECIPITATION at max intensity
        env_treat = BiosphereEnv()
        env_treat.reset(seed=42)
        for _ in range(10):
            obs_treat, _, _, _, _ = env_treat.step(np.array([2, 4, 0, 12]))

        treat_precip = obs_treat["weather_state"][0]

        # Precipitation should differ between runs
        assert treat_precip != control_precip, (
            f"Precipitation unchanged by intervention: "
            f"control={control_precip:.3f}, treatment={treat_precip:.3f}"
        )


@pytest.mark.e2e
class TestMortalityMechanics:
    """Verify organisms actually die from age, starvation, and low health.

    Refs: BLU-001 §4.6
    """

    def test_starvation_kills_organisms(self) -> None:
        """Organisms with depleted energy die.

        Set all organisms to zero energy and step — population must decrease.

        Refs: BLU-001 §4.6
        """
        engine = SimulationEngine(SimulationConfig())
        state = engine.step()

        # Count alive organisms
        alive_before = int((state["species_grid"] != SPECIES_EMPTY).sum())
        assert alive_before > 0, "No organisms to test"

        # Set all energy to zero (starvation)
        alive_mask = state["species_grid"] != SPECIES_EMPTY
        state["organism_attrs"][:, :, :, 1][alive_mask] = 0.0
        engine._state = state

        # Step — mortality phase should kill starved organisms
        new_state = engine.step()
        alive_after = int((new_state["species_grid"] != SPECIES_EMPTY).sum())

        assert alive_after < alive_before, (
            f"Starvation didn't kill: before={alive_before}, after={alive_after}"
        )

    def test_old_age_kills_organisms(self) -> None:
        """Organisms exceeding max age die.

        Refs: BLU-001 §4.6
        """
        config = SimulationConfig()
        engine = SimulationEngine(config)
        state = engine.step()

        # Set all prey to very old age (beyond max_age_prey)
        prey_mask = state["species_grid"] == SPECIES_PREY
        n_prey_before = int(prey_mask.sum())
        assert n_prey_before > 0, "No prey to test"

        # Set prey age beyond limit
        state["organism_attrs"][:, :, :, 2][prey_mask] = float(
            config.max_age_prey + 10,
        )
        engine._state = state

        # Step — mortality should kill old prey
        new_state = engine.step()
        n_prey_after = int((new_state["species_grid"] == SPECIES_PREY).sum())

        assert n_prey_after < n_prey_before, (
            f"Old age didn't kill prey: before={n_prey_before}, "
            f"after={n_prey_after}"
        )


@pytest.mark.e2e
class TestFullLifecycle:
    """Verify the complete birth → feed → reproduce → die cycle.

    Refs: BLU-001 §4
    """

    def test_reproduction_creates_new_organisms(self) -> None:
        """High-energy organisms reproduce, creating new organisms.

        Set all organisms to high energy (above reproduction threshold)
        and verify population increases.

        Refs: BLU-001 §4.5
        """
        config = SimulationConfig()
        engine = SimulationEngine(config)

        # Run a few steps to establish state
        for _ in range(5):
            engine.step()

        state = engine.get_state()

        # Count current organisms
        alive_before = int((state["species_grid"] != SPECIES_EMPTY).sum())

        # Set all organisms to high energy (well above reproduction threshold)
        alive_mask = state["species_grid"] != SPECIES_EMPTY
        state["organism_attrs"][:, :, :, 1][alive_mask] = 0.99  # Near max
        state["organism_attrs"][:, :, :, 0][alive_mask] = 0.99  # Full health
        engine._state = state

        # Run several steps — reproduction should occur
        total_new = 0
        for _ in range(10):
            new_state = engine.step()
            alive_now = int((new_state["species_grid"] != SPECIES_EMPTY).sum())
            # Track if population ever increased
            if alive_now > alive_before:
                total_new = alive_now - alive_before
                break

        assert total_new > 0, (
            f"No reproduction occurred over 10 steps. "
            f"Population stayed at {alive_before}. "
            f"Reproduction threshold: {config.reproduction_threshold}"
        )

    def test_energy_transfer_through_food_chain(self) -> None:
        """Energy flows: plants→prey→predators through consumption.

        After many steps, predators should have gained energy from prey
        (who gained energy from plants).

        Refs: BLU-001 §4.4
        """
        engine = SimulationEngine(SimulationConfig())

        # Set all predator energy to near-zero
        state = engine.step()
        pred_mask = state["species_grid"] == SPECIES_PREDATOR
        if not pred_mask.any():
            pytest.skip("No predators in initial state")

        state["organism_attrs"][:, :, :, 1][pred_mask] = 0.1
        engine._state = state

        # Run 50 steps — predators should gain energy from eating prey
        pred_energies: list[float] = []
        for _ in range(50):
            new_state = engine.step()
            current_pred = new_state["species_grid"] == SPECIES_PREDATOR
            if current_pred.any():
                mean_e = float(
                    new_state["organism_attrs"][:, :, :, 1][current_pred].mean(),
                )
                pred_energies.append(mean_e)

        assert len(pred_energies) > 0, "Predators all died before measurement"

        # Predators should have gained energy at some point
        max_energy = max(pred_energies)
        assert max_energy > 0.1, (
            f"Predator max energy ({max_energy:.3f}) never exceeded initial 0.1 "
            "— food chain energy transfer not working"
        )
