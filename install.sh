#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Biosphere Ecological Balancer — One-Click Install (Linux / Mac)   ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# Usage:  ./install.sh
#
# What this does:
#   1. Creates a Python virtual environment
#   2. Installs all dependencies
#   3. Runs tests to verify everything works
#   4. Shows you how to launch the app
#
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  🌿 Biosphere Ecological Balancer — Installer       ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Check Python version ─────────────────────────────────────────────────────
echo -e "${YELLOW}[1/4]${NC} Checking Python version..."

PYTHON=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}✗ Python 3.12+ is required but not found.${NC}"
    echo "  Install it from https://www.python.org/downloads/"
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Found $($PYTHON --version)"

# ── Create virtual environment ───────────────────────────────────────────────
echo -e "${YELLOW}[2/4]${NC} Creating virtual environment..."

if [ -d ".venv" ]; then
    echo -e "  ${GREEN}✓${NC} .venv already exists, reusing"
else
    $PYTHON -m venv .venv
    echo -e "  ${GREEN}✓${NC} Created .venv"
fi

# ── Install dependencies ────────────────────────────────────────────────────
echo -e "${YELLOW}[3/4]${NC} Installing dependencies (this may take 1-2 minutes)..."

source .venv/bin/activate
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q

echo -e "  ${GREEN}✓${NC} All packages installed"

# ── Run quick smoke test ─────────────────────────────────────────────────────
echo -e "${YELLOW}[4/4]${NC} Running quick smoke test..."

PYTHONPATH=. .venv/bin/python -c "
from biosphere.core.simulation import SimulationEngine
from biosphere.infrastructure.config import SimulationConfig
engine = SimulationEngine(SimulationConfig())
state = engine.step()
sg = state['species_grid']
plants = int((sg == 1).sum())
prey = int((sg == 2).sum())
preds = int((sg == 3).sum())
print(f'  Tick 1: {plants} plants, {prey} prey, {preds} predators')
print('  Ecosystem is alive!')
"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅  Installation complete!                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}To run the simulation:${NC}"
echo ""
echo -e "  ${CYAN}source .venv/bin/activate${NC}"
echo -e "  ${CYAN}PYTHONPATH=. python -m biosphere${NC}"
echo ""
echo -e "${BOLD}To run headless (no UI):${NC}"
echo ""
echo -e "  ${CYAN}source .venv/bin/activate${NC}"
echo -e "  ${CYAN}PYTHONPATH=. python scripts/demo.py${NC}"
echo ""
echo -e "${BOLD}To run all tests:${NC}"
echo ""
echo -e "  ${CYAN}source .venv/bin/activate${NC}"
echo -e "  ${CYAN}pytest tests/ -v${NC}"
echo ""
