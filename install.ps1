# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Biosphere Ecological Balancer — One-Click Install (Windows)       ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# Usage:  .\install.ps1
#
# If you get "scripts are disabled", run this first:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  🌿 Biosphere Ecological Balancer — Installer       ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Check Python version ─────────────────────────────────────────────────────
Write-Host "[1/4] Checking Python version..." -ForegroundColor Yellow

$pythonCmd = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 12) {
                $pythonCmd = $cmd
                Write-Host "  ✓ Found $ver" -ForegroundColor Green
                break
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Host "  ✗ Python 3.12+ is required but not found." -ForegroundColor Red
    Write-Host "    Download from https://www.python.org/downloads/"
    Write-Host "    IMPORTANT: Check 'Add Python to PATH' during install!"
    exit 1
}

# ── Create virtual environment ───────────────────────────────────────────────
Write-Host "[2/4] Creating virtual environment..." -ForegroundColor Yellow

if (Test-Path ".venv") {
    Write-Host "  ✓ .venv already exists, reusing" -ForegroundColor Green
} else {
    & $pythonCmd -m venv .venv
    Write-Host "  ✓ Created .venv" -ForegroundColor Green
}

# ── Install dependencies ────────────────────────────────────────────────────
Write-Host "[3/4] Installing dependencies (this may take 1-2 minutes)..." -ForegroundColor Yellow

& .\.venv\Scripts\Activate.ps1
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt -q

Write-Host "  ✓ All packages installed" -ForegroundColor Green

# ── Run quick smoke test ─────────────────────────────────────────────────────
Write-Host "[4/4] Running quick smoke test..." -ForegroundColor Yellow

$env:PYTHONPATH = "."
& .\.venv\Scripts\python.exe -c @"
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
"@

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅  Installation complete!                          ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "To run the simulation:" -ForegroundColor White
Write-Host ""
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "  `$env:PYTHONPATH='.' ; python -m biosphere" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run headless (no UI):" -ForegroundColor White
Write-Host ""
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "  `$env:PYTHONPATH='.' ; python scripts\demo.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run all tests:" -ForegroundColor White
Write-Host ""
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "  pytest tests/ -v" -ForegroundColor Cyan
Write-Host ""
