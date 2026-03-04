"""CLI entry point for biosphere.

Usage: python -m biosphere

Wires setup_logging + correlation ID at application entry (GOV-006 §5.1).
Refs: EVO-003, EVO-004
"""

from __future__ import annotations

import uuid

from biosphere.infrastructure.logging import set_correlation_id, setup_logging


def main() -> None:
    """Application entry point — configures logging and launches TUI."""
    setup_logging(service_name="biosphere")
    set_correlation_id(str(uuid.uuid4()))

    from biosphere.ui.app import BiosphereApp

    app = BiosphereApp()
    app.run()


if __name__ == "__main__":
    main()
