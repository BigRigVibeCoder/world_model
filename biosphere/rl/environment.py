"""Gymnasium environment wrapping the Biosphere simulation.

Refs: BLU-002 §3, EVO-002 §4.1
Provides BiosphereEnv(gym.Env) with:
  - MultiDiscrete([4, 5, 3, 25]) action space
  - Dict observation space
  - Flat (37,) action masks for MaskablePPO
  - Static codec API: build_observation, compute_action_masks, decode_action
  - Structured logging per GOV-006
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import structlog
from gymnasium import spaces

from biosphere.core.errors import InterventionError
from biosphere.core.simulation import SimulationEngine
from biosphere.core.state import (
    GRID_H,
    GRID_W,
    SPECIES_EMPTY,
    SPECIES_PLANT,
    SPECIES_PREDATOR,
    SPECIES_PREY,
    GridState,
    Intervention,
    InterventionType,
)
from biosphere.infrastructure.config import SimulationConfig
from biosphere.rl.reward import ENTROPY_WINDOW, compute_reward

# ── Constants ─────────────────────────────────────────────────────────────────

# Action space dimensions per BLU-002 §3.1
ACTION_TYPE_SIZE: int = 4
INTENSITY_SIZE: int = 5
SPECIES_DIM_SIZE: int = 3
REGION_SIZE: int = 25
ACTION_NDIMS: int = 4  # Number of dimensions in MultiDiscrete action

# Flat mask layout: [type(4) | intensity(5) | species(3) | region(25)] = 37
MASK_SIZE: int = ACTION_TYPE_SIZE + INTENSITY_SIZE + SPECIES_DIM_SIZE + REGION_SIZE

# Intensity discrete→float mapping
INTENSITY_MAP: list[float] = [0.0, 0.25, 0.5, 0.75, 1.0]

# Region index → (row, col) for 25 non-overlapping 10×10 tiles on 50×50 grid
REGION_MAP: list[tuple[int, int]] = [
    (r * 10, c * 10)
    for r in range(GRID_H // 10)
    for c in range(GRID_W // 10)
]

# Species dim → target_species for culling
CULL_SPECIES_MAP: list[int] = [SPECIES_PREY, SPECIES_PREDATOR, SPECIES_EMPTY]

# Maximum episode length
MAX_EPISODE_STEPS: int = 2000


class ActionDecodingError(InterventionError):
    """Raised when an RL action cannot be decoded to a valid Intervention.

    Refs: BLU-002 §4
    """


class BiosphereEnv(gym.Env[dict[str, np.ndarray], np.ndarray]):
    """Gymnasium environment for the Biosphere simulation.

    Wraps SimulationEngine with the RL Codec API defined in BLU-002 §3.

    Attributes:
        metadata: Gym metadata dict.
        action_space: MultiDiscrete([4, 5, 3, 25]).
        observation_space: Dict with grid_summary, population_stats,
            entropy_history, weather_state.
    """

    metadata: dict[str, Any] = {"render_modes": ["ansi"]}

    def __init__(
        self,
        config: SimulationConfig | None = None,
        render_mode: str | None = None,
    ) -> None:
        """Initialize BiosphereEnv.

        Args:
            config: SimulationConfig for the engine. Uses defaults if None.
            render_mode: Gym render mode (only "ansi" supported).

        Refs: BLU-002 §3, EVO-002 §4.1
        """
        super().__init__()

        self.render_mode = render_mode
        self._config = config or SimulationConfig()
        self._intervention_errors: list[InterventionError] = []
        self._engine = SimulationEngine(
            self._config,
            on_intervention_error=self._intervention_errors.append,
        )
        self._entropy_history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        self._current_step = 0
        self._log = structlog.get_logger(component="environment")

        # Action space: MultiDiscrete per BLU-002 §3.1
        self.action_space = spaces.MultiDiscrete(
            [ACTION_TYPE_SIZE, INTENSITY_SIZE, SPECIES_DIM_SIZE, REGION_SIZE],
        )

        # Observation space: Dict per BLU-002 §3.3
        self.observation_space = spaces.Dict(
            {
                "grid_summary": spaces.Box(
                    low=0, high=255,
                    shape=(GRID_H, GRID_W, 4), dtype=np.uint8,
                ),
                "population_stats": spaces.Box(
                    low=0.0, high=np.inf,
                    shape=(3, 3), dtype=np.float32,
                ),
                "entropy_history": spaces.Box(
                    low=-np.inf, high=np.inf,
                    shape=(ENTROPY_WINDOW,), dtype=np.float32,
                ),
                "weather_state": spaces.Box(
                    low=0.0, high=1.0,
                    shape=(4,), dtype=np.float32,
                ),
            },
        )

    # ── Gym API ───────────────────────────────────────────────────────────────

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Reset the environment to a fresh simulation state.

        Refs: BLU-002 §3
        """
        super().reset(seed=seed)
        engine_seed = seed if seed is not None else 42
        self._engine = SimulationEngine(
            self._config,
            on_intervention_error=self._intervention_errors.append,
            seed=engine_seed,
        )
        self._entropy_history = np.zeros(ENTROPY_WINDOW, dtype=np.float32)
        self._current_step = 0
        self._intervention_errors.clear()

        state = self._engine.get_state()
        obs = BiosphereEnv.build_observation(state, self._entropy_history)
        info: dict[str, Any] = {"tick": self._engine.tick}
        self._log.info(
            "env.reset",
            seed=seed or 42,
            tick=self._engine.tick,
        )
        return obs, info

    def step(
        self, action: np.ndarray,
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Execute one simulation step with the given action.

        Args:
            action: MultiDiscrete action array of shape (4,).

        Returns:
            (observation, reward, terminated, truncated, info)

        Refs: BLU-002 §3
        """
        self._intervention_errors.clear()

        # Decode action → Intervention (silently use NO_OP on error during training)
        try:
            intervention = BiosphereEnv.decode_action(action)
        except ActionDecodingError:
            intervention = Intervention(
                type=InterventionType.NO_OP,
                region_row=0,
                region_col=0,
                intensity=0.0,
            )

        state = self._engine.step(interventions=[intervention])
        self._current_step += 1

        reward, terminated = compute_reward(
            state, self._entropy_history, self._current_step,
        )

        truncated = self._current_step >= MAX_EPISODE_STEPS

        obs = BiosphereEnv.build_observation(state, self._entropy_history)
        info: dict[str, Any] = {
            "tick": self._engine.tick,
            "intervention_errors": len(self._intervention_errors),
        }

        if terminated:
            self._log.info(
                "env.terminated",
                step=self._current_step,
                reason="extinction",
            )
        elif truncated:
            self._log.info(
                "env.truncated",
                step=self._current_step,
                max_steps=MAX_EPISODE_STEPS,
            )

        return obs, reward, terminated, truncated, info

    def action_masks(self) -> np.ndarray:
        """Return action mask for MaskablePPO.

        Returns:
            Flat bool array of shape (37,).

        Refs: BLU-002 §3.2
        """
        state = self._engine.get_state()
        return BiosphereEnv.compute_action_masks(state)

    def render(self) -> np.ndarray | str | list[np.ndarray | str] | None:  # type: ignore[override]
        """Render the environment as ANSI text.

        Refs: EVO-002 §4.3
        """
        if self.render_mode != "ansi":
            return None

        state = self._engine.get_state()
        sg = state["species_grid"]
        emoji_map = {
            SPECIES_EMPTY: "·",
            SPECIES_PLANT: "🌱",
            SPECIES_PREY: "🐇",
            SPECIES_PREDATOR: "🐺",
        }

        lines: list[str] = []
        for r in range(GRID_H):
            row_chars: list[str] = []
            for c in range(GRID_W):
                # Show the highest-trophic species present
                cell_species = sg[r, c]
                max_species = int(cell_species.max())
                row_chars.append(emoji_map.get(max_species, "?"))
            lines.append("".join(row_chars))

        return "\n".join(lines)

    # ── Static Codec API (BLU-002 §3.5) ──────────────────────────────────────

    @staticmethod
    def build_observation(
        state: GridState, entropy_history: np.ndarray,
    ) -> dict[str, np.ndarray]:
        """Build observation dict from GridState.

        Args:
            state: Current simulation GridState.
            entropy_history: Rolling entropy window, shape (100,).

        Returns:
            Dict with grid_summary, population_stats, entropy_history,
            weather_state matching the observation_space spec.

        Refs: BLU-002 §3.3, §3.5
        """
        sg = state["species_grid"]
        oa = state["organism_attrs"]
        weather = state["weather"]

        # grid_summary: (H, W, 4) uint8 — species counts per cell
        grid_summary = np.zeros((GRID_H, GRID_W, 4), dtype=np.uint8)
        for sid in range(4):
            grid_summary[:, :, sid] = (sg == sid).sum(axis=2).astype(np.uint8)

        # population_stats: (3, 3) float32 — [species][mean_health, mean_energy, count]
        pop_stats = np.zeros((3, 3), dtype=np.float32)
        for i, sid in enumerate([SPECIES_PLANT, SPECIES_PREY, SPECIES_PREDATOR]):
            mask = sg == sid
            count = float(mask.sum())
            pop_stats[i, 2] = count
            if count > 0:
                pop_stats[i, 0] = float(oa[:, :, :, 0][mask].mean())
                pop_stats[i, 1] = float(oa[:, :, :, 1][mask].mean())

        # weather_state: (4,) float32 — mean precip, mean sun, std precip, std sun
        weather_state = np.array([
            float(weather[:, :, 0].mean()),
            float(weather[:, :, 1].mean()),
            float(weather[:, :, 0].std()),
            float(weather[:, :, 1].std()),
        ], dtype=np.float32)

        return {
            "grid_summary": grid_summary,
            "population_stats": pop_stats,
            "entropy_history": entropy_history.copy(),
            "weather_state": weather_state,
        }

    @staticmethod
    def compute_action_masks(state: GridState) -> np.ndarray:
        """Compute flat action mask for MaskablePPO.

        Mask layout: [type(4) | intensity(5) | species(3) | region(25)]

        Masking rules per BLU-002 §3.2:
        - species[0] (prey): False if prey population == 0
        - species[1] (predator): False if predator population == 0
        - species[2]: always False (unused slot)
        - All other dimensions: always True

        Refs: BLU-002 §3.2, §3.5
        """
        sg = state["species_grid"]
        mask = np.ones(MASK_SIZE, dtype=bool)

        # Species dimension starts at offset ACTION_TYPE_SIZE + INTENSITY_SIZE = 9
        species_offset = ACTION_TYPE_SIZE + INTENSITY_SIZE

        # Prey: mask if extinct
        if not (sg == SPECIES_PREY).any():
            mask[species_offset + 0] = False

        # Predator: mask if extinct
        if not (sg == SPECIES_PREDATOR).any():
            mask[species_offset + 1] = False

        # Unused slot: always masked
        mask[species_offset + 2] = False

        return mask

    @staticmethod
    def decode_action(action: np.ndarray) -> Intervention:
        """Decode a MultiDiscrete action to a domain Intervention.

        Args:
            action: Array of shape (4,) from the action space.

        Returns:
            Valid Intervention instance.

        Raises:
            ActionDecodingError: If the action cannot be decoded.

        Refs: BLU-002 §3.1, §3.5
        """
        if len(action) != ACTION_NDIMS:
            raise ActionDecodingError(
                f"Action must have 4 dimensions, got {len(action)}",
            )

        type_idx = int(action[0])
        intensity_idx = int(action[1])
        species_idx = int(action[2])
        region_idx = int(action[3])

        # Validate ranges
        if not (0 <= type_idx < ACTION_TYPE_SIZE):
            raise ActionDecodingError(
                f"Invalid action type index: {type_idx}",
            )
        if not (0 <= intensity_idx < INTENSITY_SIZE):
            raise ActionDecodingError(
                f"Invalid intensity index: {intensity_idx}",
            )
        if not (0 <= region_idx < REGION_SIZE):
            raise ActionDecodingError(
                f"Invalid region index: {region_idx}",
            )

        intervention_type = InterventionType(type_idx)
        intensity = INTENSITY_MAP[intensity_idx]
        region_row, region_col = REGION_MAP[region_idx]

        # Determine target species for CULL
        target_species = SPECIES_EMPTY
        if intervention_type == InterventionType.CULL_SPECIES:
            if not (0 <= species_idx < len(CULL_SPECIES_MAP)):
                raise ActionDecodingError(
                    f"Invalid species index for cull: {species_idx}",
                )
            target_species = CULL_SPECIES_MAP[species_idx]

        return Intervention(
            type=intervention_type,
            region_row=region_row,
            region_col=region_col,
            intensity=intensity,
            target_species=target_species,
        )
