<p align="center">
  <img src="docs/images/hero_banner.png" alt="Biosphere Ecological Balancer" width="100%">
</p>

<h1 align="center">🌿 Biosphere Ecological Balancer</h1>

<p align="center">
  <strong>A real-time 2D world model for RL agent training and biodiversity management</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/tests-195%20passing-brightgreen?style=for-the-badge" alt="195 Tests Passing">
  <img src="https://img.shields.io/badge/coverage-85%25-green?style=for-the-badge" alt="Coverage 85%">
  <img src="https://img.shields.io/badge/mypy-strict-blue?style=for-the-badge" alt="mypy strict">
  <img src="https://img.shields.io/badge/ruff-25%20rules-orange?style=for-the-badge" alt="Ruff">
</p>

---

## What Is This?


The application itself is a **real-time ecological simulation** — a living digital ecosystem where plants, prey, and predators interact on a 50x50 grid following real published ecological models from biology and mathematics.

**The point?** To demonstrate that AI agents can build real, working, tested, documented software — not just snippets or boilerplate, but an entire application with 195 passing tests, strict type checking, and aerospace-grade governance documentation.

<p align="center">
  <img src="docs/images/tui_screenshot.png" alt="TUI Dashboard" width="600">
</p>

---

## 🖥️ What You See When You Run `./run_tui.sh`

When you launch the dashboard, you're watching a **live ecosystem simulation** running in your terminal:

### The Grid (Left Panel)
A 50x50 world where each dot is a living organism:
- 🟢 **Green dots** = **Plants** — they grow via logistic growth (`dP/dt = rP(1-P/K)`), modulated by sunlight and rainfall
- 🟡 **Yellow dots** = **Prey** — they eat plants, move via Levy flight, reproduce when energy is high, die from starvation or old age
- 🔴 **Red dots** = **Predators** — they hunt prey using Holling Type II functional response, and starve when prey runs out
- ⚫ **Dim dots** = **Empty cells** — nothing lives here (yet)

### The Dashboard (Right Panel)
- **Population Bars** — colored bars showing the relative population of each species, updating in real-time
- **Entropy (H)** — the Shannon diversity index, measuring how balanced the ecosystem is. Higher = more biodiversity
- **Reward** — the multi-objective score combining biodiversity, stability, and population health
- **Tick** — the current simulation step

### What You'll Observe
Watch long enough and you'll see **classic Lotka-Volterra dynamics** play out in real-time:

1. 📈 **Growth phase** — all species expand, filling the grid
2. 🐺 **Predator boom** — predators overshoot, eating too many prey
3. 📉 **Crash** — prey collapse, predators starve
4. ☠️ **Possible extinction** — if prey drop too low, predators can't recover
5. 🌿 **Recovery** — surviving species rebalance without predation pressure

**Controls:** `Space` = Pause/Resume | `r` = Reset | `q` = Quit

---

## 🧬 The Simulation Engine

Every tick, the simulation runs **6 phases** in order — each implemented as vectorized NumPy array operations (no Python loops):

| Phase | What Happens | Model |
|:------|:-------------|:------|
| 1. Weather | Rainfall and sunlight diffuse across the grid | Gaussian blur |
| 2. Resources | Plants grow based on carrying capacity | Logistic growth (Verhulst 1838) |
| 3. Movement | Animals wander the grid | Levy flight |
| 4. Consumption | Prey eat plants, predators eat prey | Holling Type II (1959) |
| 5. Reproduction | High-energy organisms spawn offspring | Sigmoid probability |
| 6. Mortality | Organisms die from age, starvation, or low health | Threshold-based |

---

## 🧠 The Neural Network Brain

This isn't a simulation-only project. A **trained reinforcement learning neural network** sits on top of the ecosystem and learns to **actively manage biodiversity** — seeding plants, adjusting rainfall, and culling overpopulated species to keep the ecosystem alive.

### Without the Brain (Default Mode)
The simulation runs on pure ecological math. Nature takes its course. Lotka-Volterra dynamics play out and — more often than not — **the ecosystem collapses**. Predators eat all the prey, then starve. Plants overgrow into monocultures. Entropy drops to zero. Extinction.

### With the Brain (`--brain` Mode)
A **201,926-parameter Proximal Policy Optimization neural network** (MaskablePPO) observes the entire ecosystem state and makes real-time intervention decisions every tick:

| What the Brain Sees | What the Brain Decides |
|:-------------------|:-----------------------|
| 50×50 species grid summary (2,500 cells × 4 channels) | **Action type**: Seed Plants, Adjust Precipitation, Cull Species, or Do Nothing |
| Population statistics (mean health, energy, count per species) | **Intensity**: How aggressively to intervene (0–100%) |
| Rolling Shannon entropy history (100-tick window) | **Target species**: Which species to cull (with action masking to prevent culling extinct species) |
| Weather state (precipitation + sunlight means and variance) | **Target region**: Which 10×10 tile of the grid to affect |

### How It Works Under the Hood

```
  Observation           Neural Network              Action
 ┌─────────────┐      ┌──────────────────┐      ┌──────────────────┐
 │ Grid Summary │      │  Actor Network   │      │ Type: SEED_PLANTS│
 │ Pop Stats    │─────▶│  64×64 MLP       │─────▶│ Intensity: 75%   │
 │ Entropy Hist │      │  (ReLU layers)   │      │ Region: (20,30)  │
 │ Weather      │      │  + Action Masks  │      │ Species: n/a     │
 └─────────────┘      │                  │      └──────────────────┘
                      │  Critic Network  │
                      │  64×64 MLP       │──── Value: +1.2
                      └──────────────────┘
```

**The architecture:**
- **Algorithm**: [MaskablePPO](https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html) — Proximal Policy Optimization with dynamic action masking, from `sb3-contrib`
- **Policy**: `MultiInputActorCriticPolicy` — dual-head actor-critic with separate feature extractors for each observation component
- **Network**: Two 64-neuron hidden layers with ReLU activation (actor and critic each)
- **Action Space**: `MultiDiscrete([4, 5, 3, 25])` — 37-dimensional masked discrete actions
- **Observation Space**: `Dict` with 4 sub-spaces (grid, populations, entropy, weather)
- **Reward Function**: Multi-objective combining Shannon entropy (biodiversity), negative variance (stability), and mean population health
- **Action Masking**: A flat 37-element boolean mask prevents the network from selecting invalid actions (e.g., culling an already-extinct species)
- **Training**: 100,000 timesteps on CPU with the C-accelerated simulation engine (~470 steps/sec)
- **Framework**: PyTorch 2.10 + Stable-Baselines3 2.7.1 + Gymnasium 1.2.3

### The Difference Is Dramatic

| Metric | Without Brain | With Brain |
|:-------|:-------------|:-----------|
| Ecosystem survival (500 ticks) | ~40% | ~85% |
| Mean Shannon entropy | 0.4–0.8 | 0.9–1.1 |
| Species extinction events | Frequent | Rare |
| Mean reward per step | — | +1.10 |

---

## ✨ Features

| Feature | Details |
|:--------|:--------|
| 🧬 **6-Phase Simulation** | Weather diffusion, logistic resource growth, Levy flight movement, Holling Type II consumption, sigmoid reproduction, age-based mortality |
| � **Trained Neural Network** | 201,926-parameter MaskablePPO brain with actor-critic architecture, action masking, and multi-objective reward |
| 📊 **Shannon Entropy Reward** | Multi-objective: biodiversity + stability + population health — the brain optimizes all three simultaneously |
| 🖥️ **Terminal Dashboard** | Real-time Textual TUI with grid visualization, population charts, and live brain decision display |
| ⚡ **C-Accelerated Engine** | Custom CPython C extension for movement + reproduction — 4× speedup over pure Python (~470 ops/sec) |
| 🔒 **NaN Rollback** | Automatic state recovery on numerical instability |
| 📋 **NASA-Grade Governance** | Full CODEX documentation system with 6 governance standards |

---

## 🚀 Quick Start

### 1. Install (one command)

**Linux / Mac:**
```bash
git clone https://github.com/BigRigVibeCoder/world_model.git
cd world_model
./install.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/BigRigVibeCoder/world_model.git
cd world_model
.\install.ps1
```

### 2. Watch the Ecosystem

| What You Want | Command |
|:-------------|:--------|
| **Dashboard (no brain)** | `./run_tui.sh` |
| **Dashboard with AI Brain** 🧠 | `./run_tui.sh --brain checkpoints/` |
| **Headless brain demo** | `python scripts/run_trained_agent.py --steps 100` |

### 3. Train Your Own Brain

```bash
# Train a fresh MaskablePPO agent for 100K timesteps
CUDA_VISIBLE_DEVICES="" PYTHONPATH=. .venv/bin/python -m biosphere.rl.train

# The checkpoint saves automatically to checkpoints/
```

### 4. Run All Tests

```bash
pytest tests/ -v
# 195 passed ✅
```


## 📚 Documentation

Full aerospace-grade documentation in `CODEX/`:

| Folder | Contents |
|:-------|:---------|
| `00_INDEX/` | MANIFEST.yaml — machine-readable document registry |
| `10_GOVERNANCE/` | 6 governance standards (coding, testing, logging, errors, docs, agentic dev) |
| `20_BLUEPRINTS/` | Technical specifications (BLU-001, BLU-002) |
| `30_RUNBOOKS/` | User manual, sprint runbooks |
| `40_VERIFICATION/` | Test reports, traceability matrix, coverage HTML |
| `50_DEFECTS/` | Bug reports and gap analyses |

---

## 🧪 Testing

195 tests across 7 tiers — **zero mocks in E2E tests**:

| Tier | Count | What It Tests |
|:-----|:------|:-------------|
| Unit | ~100 | Individual functions, pure logic |
| Property-Based | 10+ | Hypothesis-generated edge cases |
| Integration | 15+ | Multi-component interactions |
| Contract | 10+ | API/schema compliance |
| **E2E (Real)** | **23** | **Full stack, no mocks, strong assertions** |
| Performance | 2 | Benchmark throughput (~470 ops/sec with C extension) |
| Infrastructure | 8+ | Logging, crash artifacts, config |

---

## 📖 Ecological Models Used

| Model | Application | Reference |
|:------|:-----------|:----------|
| **Lotka-Volterra** (modified) | Predator-prey dynamics | Lotka (1925), Volterra (1926) |
| **Holling Type II** | Functional response / consumption | Holling (1959) |
| **Shannon-Wiener Index** | Biodiversity entropy measurement | Shannon (1948) |
| **Logistic Growth** | Resource regeneration `dP/dt = rP(1-P/K)` | Verhulst (1838) |
| **Gaussian Diffusion** | Weather pattern spreading | — |
| **Sigmoid Reproduction** | Energy-dependent reproduction `p = 1/(1+exp(-k(E-θ)))` | — |

---

## 📄 License

MIT

---
