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

This is a **complete, production-grade application built entirely by AI agents** under the direction of a human Architect. No line of code was written by hand — every file, test, governance document, and deployment script was generated through an **Agentic Development** workflow.

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

## ✨ Features

| Feature | Details |
|:--------|:--------|
| 🧬 **6-Phase Simulation** | Weather diffusion, logistic resource growth, Levy flight movement, Holling Type II consumption, sigmoid reproduction, age-based mortality |
| 🤖 **RL Agent** | MaskablePPO via Stable-Baselines3 with action masking for invalid interventions |
| 📊 **Shannon Entropy Reward** | Multi-objective: biodiversity + stability + population health |
| 🖥️ **Terminal Dashboard** | Real-time Textual TUI with grid visualization and population charts |
| ⚡ **Vectorized NumPy** | No Python loops over cells — pure array operations for ~100+ steps/sec |
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
| **Dashboard (TUI)** | `./run_tui.sh` |
| **Headless demo** | `./run.sh` |

### 3. Run All Tests

```bash
pytest tests/ -v
# 195 passed ✅
```

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
| Performance | 2 | Benchmark throughput (~120 ops/sec) |
| Infrastructure | 8+ | Logging, crash artifacts, config |

### E2E Tests Prove Real Ecosystem Behavior:

- ✅ Predator-prey populations **oscillate** (Lotka-Volterra verified)
- ✅ Resources **deplete** under consumption and **recover** via logistic growth
- ✅ Weather **diffuses** via Gaussian blur
- ✅ Shannon entropy correctly **ranks** biodiversity
- ✅ Interventions cause **measurable** state changes
- ✅ Organisms **die** from starvation, old age, and low health
- ✅ Reproduction **creates** new organisms when energy is high
- ✅ Energy **flows** through the food chain (plants → prey → predators)

```bash
# Run everything
pytest tests/ -v

# Run only E2E tests
pytest tests/e2e/ -v

# Run with coverage
pytest tests/ --cov=biosphere --cov-report=html
```

---

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

## 🔧 Code Quality Tools

```bash
ruff check biosphere/ tests/     # 25 rule categories
mypy --strict biosphere/          # Full type safety
bandit -r biosphere/              # Security scanning
radon cc biosphere/ -a -nc        # Cyclomatic complexity
mutmut run                        # Mutation testing
```

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

<p align="center">
  <em>Built with the <a href="CODEX/10_GOVERNANCE/">Agentic Architect</a> methodology — an AI-human collaborative development framework.</em>
</p>
