"""CLI entry point for biosphere.

Usage: python -m biosphere

Wires setup_logging + correlation ID at application entry (GOV-006 §5.1).
Refs: EVO-003, EVO-004
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from biosphere.infrastructure.logging import set_correlation_id, setup_logging


def main() -> None:
    """Application entry point — configures logging and launches TUI."""
    parser = argparse.ArgumentParser(description="Biosphere Ecological Balancer")
    parser.add_argument(
        "--brain",
        type=str,
        default=None,
        help="Path to a trained MaskablePPO .zip checkpoint to use as the RL agent",
    )
    args = parser.parse_args()

    setup_logging(service_name="biosphere")
    set_correlation_id(str(uuid.uuid4()))

    from biosphere.ui.app import BiosphereApp

    app = BiosphereApp(brain_path=args.brain)
    app.run()


if __name__ == "__main__":
    main()
