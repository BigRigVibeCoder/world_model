"""CLI entry point for biosphere.

Usage: python -m biosphere [--train|--simulate|--tui]

Wires setup_logging + correlation ID at application entry (GOV-006 §5.1).
Refs: EVO-003, DEF-001-13
"""

from __future__ import annotations

import uuid

from biosphere.infrastructure.logging import set_correlation_id, setup_logging


def main() -> None:
    """Application entry point — configures logging and runs CLI."""
    setup_logging(service_name="biosphere")
    set_correlation_id(str(uuid.uuid4()))

    # TODO(EVO-003): Add argparse for --train, --simulate, --tui modes
    print("biosphere CLI ready (use --train, --simulate, or --tui)")


if __name__ == "__main__":
    main()
