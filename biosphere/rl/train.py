"""MaskablePPO training pipeline for BiosphereEnv.

Refs: BLU-002 §3, EVO-002 §4.2
Handles:
  - Config-driven hyperparameters from YAML
  - Action masking via BiosphereEnv.action_masks()
  - Checkpoint saving with correlation IDs (GOV-006)

mypy: sb3-contrib lacks complete type stubs, so we use targeted ignores.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import structlog
import yaml
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from biosphere.infrastructure.config import SimulationConfig
from biosphere.rl.environment import BiosphereEnv


def _mask_fn(env: BiosphereEnv) -> Any:
    """Extract action masks from the environment for MaskablePPO."""
    return env.action_masks()


def load_training_config(path: str | Path = "config/training.yaml") -> dict[str, Any]:
    """Load training hyperparameters from YAML.

    Args:
        path: Path to training config YAML.

    Returns:
        Dictionary of hyperparameters.

    Refs: EVO-002 §4.2
    """
    config_path = Path(path)
    if not config_path.exists():
        msg = f"Training config not found: {config_path}"
        raise FileNotFoundError(msg)

    with open(config_path, encoding="utf-8") as f:
        return dict(yaml.safe_load(f))


def train(
    sim_config: SimulationConfig | None = None,
    training_config_path: str | Path = "config/training.yaml",
    total_timesteps: int | None = None,
) -> Path:
    """Run MaskablePPO training on BiosphereEnv.

    Args:
        sim_config: Optional SimulationConfig for the environment.
        training_config_path: Path to training YAML config.
        total_timesteps: Override total timesteps (takes precedence over YAML).

    Returns:
        Path to the saved model checkpoint.

    Refs: BLU-002 §3, EVO-002 §4.2
    """
    # Load training config
    train_cfg = load_training_config(training_config_path)

    # Create environment with action masking wrapper
    env = BiosphereEnv(config=sim_config)
    wrapped_env = ActionMasker(env, _mask_fn)  # type: ignore[arg-type]

    # Resolve timesteps
    n_timesteps = total_timesteps or int(train_cfg.get("total_timesteps", 100_000))

    # Build policy kwargs
    policy_kwargs: dict[str, Any] = {}
    if "policy_kwargs" in train_cfg:
        policy_kwargs = dict(train_cfg["policy_kwargs"])

    # Create MaskablePPO model
    model = MaskablePPO(
        policy=str(train_cfg.get("policy", "MultiInputPolicy")),
        env=wrapped_env,
        learning_rate=float(train_cfg.get("learning_rate", 3e-4)),
        n_steps=int(train_cfg.get("n_steps", 256)),
        batch_size=int(train_cfg.get("batch_size", 64)),
        n_epochs=int(train_cfg.get("n_epochs", 10)),
        gamma=float(train_cfg.get("gamma", 0.99)),
        gae_lambda=float(train_cfg.get("gae_lambda", 0.95)),
        clip_range=float(train_cfg.get("clip_range", 0.2)),
        ent_coef=float(train_cfg.get("ent_coef", 0.01)),
        vf_coef=float(train_cfg.get("vf_coef", 0.5)),
        max_grad_norm=float(train_cfg.get("max_grad_norm", 0.5)),
        policy_kwargs=policy_kwargs,
        verbose=0,
    )

    log = structlog.get_logger(component="training")
    log.info(
        "training.start",
        total_timesteps=n_timesteps,
        learning_rate=float(train_cfg.get("learning_rate", 3e-4)),
    )

    # Train
    model.learn(total_timesteps=n_timesteps)

    log.info("training.complete", total_timesteps=n_timesteps)

    # Save checkpoint with correlation ID (GOV-006)
    correlation_id = uuid.uuid4().hex[:12]
    checkpoint_dir = Path(str(train_cfg.get("checkpoint_dir", "checkpoints")))
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / f"biosphere_ppo_{correlation_id}"
    model.save(str(checkpoint_path))

    log.info(
        "training.checkpoint_saved",
        path=str(checkpoint_path),
        correlation_id=correlation_id,
    )

    return checkpoint_path
