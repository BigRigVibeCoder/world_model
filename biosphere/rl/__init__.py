"""Biosphere RL module — Gymnasium environment and training.

Refs: BLU-002 §3, EVO-002
"""

from biosphere.rl.environment import ActionDecodingError, BiosphereEnv
from biosphere.rl.reward import compute_reward, shannon_entropy

__all__ = [
    "ActionDecodingError",
    "BiosphereEnv",
    "compute_reward",
    "shannon_entropy",
]
