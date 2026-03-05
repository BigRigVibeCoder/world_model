#!/usr/bin/env python3
"""Run a trained MaskablePPO agent on the Biosphere simulation.

Loads a saved checkpoint and runs the trained neural network brain,
printing each action decision and the ecosystem state. This is the
"brain in action" demo.

Usage:
    python scripts/run_trained_agent.py [checkpoint_path] [--steps N]

READING GUIDE FOR INCIDENT RESPONDERS:
  1. If agent takes no actions    → check action masks (extinct species?)
  2. If checkpoint fails to load  → verify PyTorch + SB3 versions match training
  3. If rewards are always negative → check reward.py weights

REF: BLU-002 §3 (RL environment spec)
REF: EVO-005 (RL training sprint)
SEE ALSO: biosphere/rl/train.py — training pipeline that produced the checkpoint
SEE ALSO: biosphere/rl/environment.py — BiosphereEnv wrapper
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Suppress verbose logging for clean demo output
logging.disable(logging.WARNING)


def main() -> None:
    """Load trained agent and run demo episodes."""
    parser = argparse.ArgumentParser(
        description="Run a trained MaskablePPO agent on the Biosphere simulation",
    )
    parser.add_argument(
        "checkpoint",
        nargs="?",
        default=None,
        help="Path to saved .zip checkpoint (auto-finds latest if omitted)",
    )
    parser.add_argument(
        "--steps", type=int, default=200,
        help="Number of simulation steps to run (default: 200)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility",
    )
    args = parser.parse_args()

    # Force CPU (avoids CUDA compatibility issues)
    import os
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

    import numpy as np
    import structlog
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
    )

    from sb3_contrib import MaskablePPO

    from biosphere.core.state import SPECIES_PLANT, SPECIES_PREDATOR, SPECIES_PREY
    from biosphere.rl.environment import BiosphereEnv

    # ── Find checkpoint ──────────────────────────────────────────────────────
    if args.checkpoint:
        ckpt_path = Path(args.checkpoint)
    else:
        # Auto-find latest checkpoint
        ckpt_dir = Path("checkpoints")
        if not ckpt_dir.exists():
            print("ERROR: No checkpoints/ directory found. Train first:")
            print("  python -c 'from biosphere.rl.train import train; train()'")
            sys.exit(1)
        zips = sorted(ckpt_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime)
        if not zips:
            print("ERROR: No .zip checkpoints found in checkpoints/")
            sys.exit(1)
        ckpt_path = zips[-1]

    print("=" * 70)
    print("  Biosphere RL Agent Demo — Trained Neural Network Brain")
    print("=" * 70)
    print(f"  Checkpoint : {ckpt_path}")
    print(f"  Steps      : {args.steps}")
    print(f"  Seed       : {args.seed}")
    print("=" * 70)

    # ── Load model ────────────────────────────────────────────────────────────
    print("\nLoading trained model...")
    model = MaskablePPO.load(str(ckpt_path))
    print(f"  Policy: {model.policy.__class__.__name__}")
    n_params = sum(p.numel() for p in model.policy.parameters())
    print(f"  Parameters: {n_params:,}")
    print(f"  Architecture: {model.policy.net_arch}")

    # ── Create environment ────────────────────────────────────────────────────
    env = BiosphereEnv()
    obs, info = env.reset(seed=args.seed)

    action_names = ["NO_OP", "SEED_PLANTS", "ADJUST_PRECIP", "CULL_SPECIES"]
    intensity_names = ["0%", "25%", "50%", "75%", "100%"]
    species_names = ["Prey", "Predator", "—"]

    # ── Run trained agent ─────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print(f"{'Step':>5} | {'Action':<16} | {'Intensity':>9} | {'Reward':>8} | "
          f"{'Plants':>7} {'Prey':>7} {'Pred':>7}")
    print("-" * 70)

    total_reward = 0.0
    for step in range(args.steps):
        # Get action masks and predict
        masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)

        # Decode action for display
        a_type = int(action[0])
        a_intensity = int(action[1])
        a_species = int(action[2])
        action_str = action_names[a_type]
        if a_type == 3:  # CULL
            action_str += f"({species_names[a_species]})"

        # Step environment
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

        # Count populations
        sg = env._engine._state["species_grid"]  # noqa: SLF001
        n_plant = int((sg == SPECIES_PLANT).sum())
        n_prey = int((sg == SPECIES_PREY).sum())
        n_pred = int((sg == SPECIES_PREDATOR).sum())

        # Print every 10th step (or first/last)
        if step % 10 == 0 or step == args.steps - 1 or terminated:
            print(f"{step:>5} | {action_str:<16} | "
                  f"{intensity_names[a_intensity]:>9} | "
                  f"{reward:>+8.3f} | "
                  f"{n_plant:>7,} {n_prey:>7,} {n_pred:>7,}")

        if terminated or truncated:
            print(f"\n  Episode ended at step {step} "
                  f"({'terminated' if terminated else 'truncated'})")
            break

    # ── Summary ───────────────────────────────────────────────────────────────
    print("-" * 70)
    print(f"\n  Total reward : {total_reward:+.2f}")
    print(f"  Mean reward  : {total_reward / max(step + 1, 1):+.4f}/step")
    print(f"  Final pops   : {n_plant:,} plants, {n_prey:,} prey, {n_pred:,} predators")
    print()


if __name__ == "__main__":
    main()
