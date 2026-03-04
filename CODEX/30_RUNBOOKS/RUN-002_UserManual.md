---
id: RUN-002
title: "Biosphere User Manual"
type: reference
status: DRAFT
owner: architect
agents: [all]
tags: [runbook, user-manual, operations, getting-started]
related: [BLU-001, BLU-002, RUN-001, GOV-006]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** Dead-simple, step-by-step instructions for installing, running, and using the Biosphere Ecological Balancer. Copy-paste every command. If it doesn't work, check the Troubleshooting section at the bottom.

# RUN-002: Biosphere User Manual

---

## 🎯 One-Click Install (Recommended)

Just clone and run ONE command. It handles everything.

### Linux / Mac

```bash
git clone https://github.com/BigRigVibeCoder/world_model.git
cd world_model
./install.sh
```

### Windows (PowerShell)

```powershell
git clone https://github.com/BigRigVibeCoder/world_model.git
cd world_model
.\install.ps1
```

> **If PowerShell says "scripts are disabled"**, run this first:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

The installer will:
1. ✅ Check your Python version (3.12+ required)
2. ✅ Create a virtual environment
3. ✅ Install all dependencies
4. ✅ Run a smoke test to prove it works
5. ✅ Print instructions for launching the app

### After install — run the demo:

**Linux / Mac:**
```bash
./run.sh
```

**Windows:**
```powershell
.\run.ps1
```

You'll see 200 ticks of a living ecosystem with 🌿🐰🐺 emoji visualizations!

---

## Manual Install (Step-by-Step)
## Step 1: Make Sure You Have Python 3.12+

Open a terminal and type:

```bash
python3 --version
```

You should see `Python 3.12.x` or higher. If not, install Python 3.12 first.

---

## Step 2: Clone the Repository

```bash
git clone https://github.com/BigRigVibeCoder/world_model.git
cd world_model
```

---

## Step 3: Create a Virtual Environment

```bash
python3 -m venv .venv
```

---

## Step 4: Activate the Virtual Environment

**Linux / Mac:**
```bash
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate
```

You should see `(.venv)` at the beginning of your prompt. If you don't, try again.

---

## Step 5: Install Dependencies

```bash
pip install -e ".[dev]"
```

This installs biosphere and all development tools (pytest, ruff, mypy, etc.).

If you get errors about `numpy` or `scipy`, try:
```bash
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

---

## Step 6: Run the Tests (Sanity Check)

Before doing anything else, make sure everything works:

```bash
pytest tests/ -v
```

You should see something like `195 passed`. If tests fail, check Troubleshooting below.

---

## Step 7: Run the Simulation (Headless)

Run the simulation engine directly from Python:

```python
python3 -c "
from biosphere.core.simulation import SimulationEngine
from biosphere.infrastructure.config import SimulationConfig

engine = SimulationEngine(SimulationConfig())
for i in range(100):
    state = engine.step()
    sg = state['species_grid']
    plants = int((sg == 1).sum())
    prey = int((sg == 2).sum())
    preds = int((sg == 3).sum())
    print(f'Tick {i+1:3d} | Plants: {plants:4d} | Prey: {prey:3d} | Predators: {preds:3d}')
"
```

You'll see population counts changing every tick — that's the ecosystem running!

---

## Step 8: Run the TUI Dashboard

Launch the full terminal dashboard:

```bash
python -m biosphere
```

You'll see:
- **Left:** A 50×50 grid showing plants (🌿), prey (🐰), and predators (🐺)
- **Right:** Population bar charts
- **Bottom:** Metrics (tick count, entropy, reward)

**Controls:**
| Key | What It Does |
|:----|:-------------|
| `q` or `ESC` | Quit |
| Space | Pause / Resume |

---

## Step 9: Train the RL Agent

Train a MaskablePPO agent to manage the ecosystem:

```bash
python3 -c "
from biosphere.rl.train import train
train(total_timesteps=10_000, save_path='checkpoints/my_model')
"
```

This takes a few minutes. When done, you'll have a trained model at `checkpoints/my_model.zip`.

For a longer, better training run:
```bash
python3 -c "
from biosphere.rl.train import train
train(total_timesteps=100_000, save_path='checkpoints/long_run')
"
```

---

## Step 10: Run Static Analysis

Check code quality:

```bash
# Linting
ruff check biosphere/ tests/

# Type checking
mypy --strict biosphere/

# Security scanning
bandit -r biosphere/ -c pyproject.toml

# Complexity analysis
radon cc biosphere/ -a -nc

# Coverage report
pytest tests/ --cov=biosphere --cov-report=term-missing
```

---

## Cheat Sheet

| What You Want | Command |
|:-------------|:--------|
| Run tests | `pytest tests/ -v` |
| Run fast tests only | `pytest tests/ -v -m "not slow"` |
| Run E2E tests only | `pytest tests/e2e/ -v` |
| Launch TUI | `python -m biosphere` |
| Train agent (quick) | See Step 9 |
| Check code | `ruff check biosphere/` |
| Type check | `mypy --strict biosphere/` |
| Coverage | `pytest --cov=biosphere --cov-report=html` |
| See coverage HTML | Open `htmlcov/index.html` in browser |

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'biosphere'"

You forgot to install. Run:
```bash
pip install -e ".[dev]"
```

### "No module named 'scipy'"

```bash
pip install scipy numpy
```

### Tests fail with import errors

Make sure your virtual environment is activated:
```bash
source .venv/bin/activate
```

### TUI looks garbled

Your terminal doesn't support Unicode. Try a modern terminal:
- **Linux:** GNOME Terminal, Kitty, Alacritty
- **Mac:** iTerm2
- **Windows:** Windows Terminal (not cmd.exe)

### "Permission denied" on Linux

```bash
chmod +x .venv/bin/python3
```

### Everything is broken and I don't know why

Nuclear option — start fresh:
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

---

## File Structure (Where Things Live)

```
world_model/
├── biosphere/              # ← THE APPLICATION
│   ├── core/               #   Simulation engine + 6-phase cycle
│   │   ├── simulation.py   #   SimulationEngine class
│   │   ├── phases.py       #   Weather, growth, movement, consumption, reproduction, mortality
│   │   ├── state.py        #   GridState, species constants
│   │   └── types.py        #   Semantic type aliases
│   ├── rl/                 #   Reinforcement learning
│   │   ├── environment.py  #   BiosphereEnv (Gymnasium wrapper)
│   │   ├── reward.py       #   Shannon entropy reward function
│   │   └── train.py        #   MaskablePPO training pipeline
│   ├── ui/                 #   Terminal UI (Textual)
│   └── infrastructure/     #   Logging, errors, config
├── tests/                  # ← TESTS (195 total)
│   ├── core/               #   Unit tests
│   ├── rl/                 #   RL environment tests
│   ├── e2e/                #   End-to-end tests (no mocks!)
│   └── infrastructure/     #   Logging/config tests
├── CODEX/                  # ← DOCUMENTATION
│   ├── 10_GOVERNANCE/      #   Standards (coding, testing, logging)
│   ├── 20_BLUEPRINTS/      #   Architecture specs
│   ├── 30_RUNBOOKS/        #   This manual + sprint runbooks
│   ├── 40_VERIFICATION/    #   Test reports + coverage
│   └── 50_DEFECTS/         #   Bug reports
└── pyproject.toml          # ← Config (pytest, ruff, mypy, bandit, mutmut)
```
