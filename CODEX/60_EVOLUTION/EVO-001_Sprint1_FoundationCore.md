---
id: EVO-001
title: "Sprint 1: Foundation & Core Simulation Engine"
type: reference
status: DRAFT
owner: architect
agents: [coder, tester]
tags: [feature, architecture, project-management]
related: [BLU-001, BLU-002, RUN-001, GOV-002, GOV-003, GOV-004, GOV-005, GOV-006]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** First scope-bounded sprint for the Biosphere Ecological Balancer. Establishes project scaffolding (GOV-004/006 compliant infrastructure) and the vectorized NumPy simulation engine with GridState, Interventions, and weather/ecology update cycle. All downstream work (RL, TUI, CLI) depends on this sprint completing.

# Feature Specification: Sprint 1 — Foundation & Core Simulation Engine

## 1. Overview

| Field | Value |
|:------|:------|
| **Priority** | P0 — Critical (blocks all other sprints) |
| **Status** | DRAFT |
| **Requested By** | Architect |
| **Branch** | `feat/EVO-001-foundation-core` |
| **Estimated Scope** | Large (10+ files) |
| **Backlog Tasks** | RUN-001 Tasks 1, 2 |

## 2. Problem Statement

The Biosphere project has specifications (BLU-001) and architecture (BLU-002) but no code. Before RL training, TUI rendering, or CLI orchestration can begin, two foundational layers must exist:

1. **Project infrastructure** — Package structure, error handling (GOV-004), structured logging (GOV-006), and dependency manifest
2. **Core simulation engine** — The vectorized NumPy engine that maintains world state and processes ecological ticks

Without these, no downstream sprint can start.

## 3. Proposed Solution

### 3.1 Files to Create or Modify

| Action | File | Purpose |
|:-------|:-----|:--------| 
| CREATE | `biosphere/__init__.py` | Package root with version |
| CREATE | `biosphere/core/__init__.py` | Core module exports (GridState, SimulationEngine) |
| CREATE | `biosphere/core/state.py` | GridState TypedDict, constants, Intervention, InterventionType |
| CREATE | `biosphere/core/simulation.py` | SimulationEngine with vectorized step(), get_state(), NaN rollback |
| CREATE | `biosphere/core/errors.py` | SimulationError, InterventionError |
| CREATE | `biosphere/infrastructure/__init__.py` | Infrastructure module exports |
| CREATE | `biosphere/infrastructure/errors.py` | ApplicationError, ConfigurationError (GOV-004) |
| CREATE | `biosphere/infrastructure/logging.py` | setup_logging() with JSONL crash output (GOV-006) |
| CREATE | `biosphere/infrastructure/config.py` | SimulationConfig Pydantic model satisfying SimulationParams protocol |
| CREATE | `biosphere/rl/__init__.py` | RL module stub (empty, for package structure) |
| CREATE | `biosphere/ui/__init__.py` | UI module stub (empty, for package structure) |
| CREATE | `biosphere/cli/__init__.py` | CLI module stub (empty, for package structure) |
| CREATE | `config/simulation.yaml` | Default simulation parameters |
| CREATE | `requirements.txt` | Pinned runtime dependencies |
| CREATE | `requirements-dev.txt` | Dev dependencies (pytest, mypy, ruff, hypothesis) |
| CREATE | `tests/__init__.py` | Test package root |
| CREATE | `tests/core/__init__.py` | Core test package |
| CREATE | `tests/core/test_state.py` | Tests for GridState initialization and constants |
| CREATE | `tests/core/test_simulation.py` | Tests for SimulationEngine (step, NaN rollback, interventions) |
| CREATE | `tests/infrastructure/__init__.py` | Infrastructure test package |
| CREATE | `tests/infrastructure/test_errors.py` | Tests for error hierarchy and JSONL logging |

### 3.2 Dependencies

| Dependency | Required For | Version |
|:-----------|:------------|:--------|
| `numpy` | GridState arrays, vectorized ops | ≥1.24 |
| `scipy` | Gaussian filter for weather diffusion | ≥1.10 |
| `structlog` | GOV-006 structured logging | ≥23.1 |
| `pydantic` | SimulationConfig validation | ≥2.0 |
| `pyyaml` | YAML config loading | ≥6.0 |

**Dev dependencies:** `pytest`, `pytest-benchmark`, `pytest-cov`, `hypothesis`, `mypy`, `ruff`

No external services or infrastructure required. Pure local execution.

## 4. Acceptance Criteria

> **"How do we know this is done?"**

### 4.1 Foundation (Task 1)

- [ ] `python -c "from biosphere.core import state, simulation, errors"` succeeds
- [ ] `python -c "from biosphere.infrastructure import logging, errors, config"` succeeds
- [ ] `mypy --strict biosphere/` returns zero errors
- [ ] Raising `ApplicationError` produces JSONL entry in `logs/crashes/`
- [ ] `SimulationConfig` Pydantic model satisfies `SimulationParams` protocol

### 4.2 Core Engine (Task 2)

- [ ] `SimulationEngine.__init__` validates all parameter ranges (defense in depth)
- [ ] `SimulationEngine.step()` returns deep copy of GridState
- [ ] `SimulationEngine.get_state()` returns deep copy of GridState
- [ ] NaN rollback restores previous state and dampens energy by 0.9
- [ ] Two consecutive NaN states raise `SimulationError`
- [ ] Invalid interventions invoke callback (not raise)
- [ ] `pytest-benchmark` shows ≥1000 steps/sec for 50×50 grid
- [ ] Hypothesis property tests confirm energy conservation across 100 steps
- [ ] `GridState` uses mixed dtypes: `uint8` for species_grid, `float32` for continuous fields

## 5. Test Plan

| Test Type | What to Test | Expected Result |
|:----------|:------------|:----------------|
| Unit | `GridState` creation and shape validation | All arrays match documented shapes and dtypes |
| Unit | `Intervention.validate()` with valid/invalid inputs | Raises `InterventionError` on invalid, passes on valid |
| Unit | `SimulationEngine.__init__` parameter validation | `SimulationError` on out-of-range params |
| Unit | `SimulationEngine.step()` basic tick | State changes, tick increments, deep copy returned |
| Unit | `SimulationEngine.step()` with interventions | Valid interventions modify state, invalid ones invoke callback |
| Unit | NaN rollback mechanism | Restores previous state, dampens energy |
| Unit | `ApplicationError` → JSONL logging | JSONL file created in `logs/crashes/` |
| Benchmark | `step()` performance on 50×50 grid | ≥1000 steps/sec |
| Property | Energy conservation (Hypothesis) | Total energy in == total energy out ± epsilon over 100 steps |
| Static | `mypy --strict biosphere/` | Zero errors |
| Static | `ruff check biosphere/` | Zero errors |

**Test commands:**

```bash
# Unit + property tests
pytest tests/ -v --tb=short

# Coverage
pytest tests/ --cov=biosphere --cov-report=term-missing

# Performance
pytest tests/core/test_simulation.py -v --benchmark-only

# Static analysis
mypy --strict biosphere/
ruff check biosphere/
```

## 6. Checkpoints

| Checkpoint | What Architect Reviews |
|:-----------|:----------------------|
| After spec approval | Does this capture the full scope of Tasks 1-2? |
| After `biosphere/infrastructure/` | Do error handling and logging match GOV-004/006? |
| After `biosphere/core/state.py` | Do GridState shapes/dtypes match BLU-002 §2.1? |
| After `SimulationEngine.step()` | Does the vectorized update cycle look correct? |
| After all tests pass | Coverage ≥80%? Benchmark ≥1000 steps/sec? |
| Before merge | Ready for main? Clean diff? |

## 7. Risks & Open Questions

| Risk / Question | Mitigation / Answer |
|:----------------|:-------------------|
| Performance budget (1000 steps/sec) may be tight with full ecology rules | Profile early; use vectorized NumPy exclusively (no Python loops over cells) |
| `scipy.ndimage.gaussian_filter` may be slow on 50×50 | Benchmark in isolation; consider pre-computed kernel if needed |
| NaN rollback only retains 1 previous state | Sufficient for v1.0; extended rollback buffer if needed in Sprint 3 |
| `organism_attrs` age as float32 | Integer values stored as float for arithmetic; documented in BLU-002 |

## 8. Definition of Done

This sprint is **complete** when:

1. All acceptance criteria (§4) are met
2. All tests (§5) pass
3. `mypy --strict` and `ruff` return zero errors
4. Architect UAT approves at final checkpoint
5. Branch `feat/EVO-001-foundation-core` merged to `master`
