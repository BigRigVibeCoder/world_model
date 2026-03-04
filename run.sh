#!/usr/bin/env bash
# Run the Biosphere demo — just double-click or type: ./run.sh
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
PYTHONPATH=. python scripts/demo.py
