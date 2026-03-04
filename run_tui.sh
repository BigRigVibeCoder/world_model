#!/usr/bin/env bash
# Launch the Biosphere TUI dashboard — just type: ./run_tui.sh
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
LOG_LEVEL=WARNING PYTHONPATH=. python -m biosphere
