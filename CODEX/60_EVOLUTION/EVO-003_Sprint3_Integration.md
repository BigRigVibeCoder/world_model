---
id: EVO-003
title: "Sprint 3: CLI Integration & Governance Audit"
type: reference
status: DRAFT
owner: architect
agents: [coder, tester]
tags: [feature, architecture, project-management, verification]
related: [BLU-001, BLU-002, RUN-001, EVO-001, EVO-002, GOV-002, GOV-003, GOV-005]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** Final sprint for the Biosphere Ecological Balancer. Wires simulation engine, RL agent, and TUI into a unified CLI entry point, then runs full GOV-002 governance audit. After this sprint, `python -m biosphere` launches a working application.

# Feature Specification: Sprint 3 — CLI Integration & Governance Audit

## 1. Overview

| Field | Value |
|:------|:------|
| **Priority** | P1 — High |
| **Status** | DRAFT |
| **Requested By** | Architect |
| **Branch** | `feat/EVO-003-cli-verification` |
| **Estimated Scope** | Medium (5 files) |
| **Backlog Tasks** | RUN-001 Tasks 6, 7 |
| **Depends On** | EVO-001, EVO-002 (both must be merged) |

## 2. Problem Statement

After Sprints 1-2, all components exist in isolation — the simulation engine, RL environment, training pipeline, and TUI dashboard. They need a unified entry point that:

1. **Wires dependencies** — Config → Engine → Env → Agent → TUI
2. **Provides CLI modes** — `train` (RL training) and `run` (inference + TUI)
3. **Passes governance audit** — GOV-002 test suite, GOV-003 static analysis, coverage targets

## 3. Proposed Solution

### 3.1 Files to Create or Modify

| Action | File | Purpose |
|:-------|:-----|:--------|
| CREATE | `biosphere/__main__.py` | CLI entry point with `train` and `run` subcommands |
| CREATE | `tests/conftest.py` | Shared test fixtures (engine, env, config factories) |
| CREATE | `tests/test_integration.py` | End-to-end integration tests |
| CREATE | `CODEX/40_VERIFICATION/VER-001_FinalReport.md` | GOV-002 verification report |
| MODIFY | `biosphere/cli/__init__.py` | Export CLI entry points |

### 3.2 Dependencies

| Dependency | Required For |
|:-----------|:------------|
| **EVO-001 merged** | Core engine, infrastructure |
| **EVO-002 merged** | RL env, training, TUI |
| All runtime deps installed | Full integration |

## 4. Acceptance Criteria

### 4.1 CLI Integration (Task 6)

- [ ] `python -m biosphere train` starts RL training and saves checkpoints
- [ ] `python -m biosphere run` opens TUI with pre-trained agent
- [ ] Agent actions visible in 'Actions Feed' panel of TUI
- [ ] CLI loads config from `config/simulation.yaml` and `config/training.yaml`
- [ ] CLI wires `on_intervention_error` callback to structured logger (BLU-002 §4)
- [ ] Inference loop uses RL Codec API static methods (BLU-002 §3.5)

### 4.2 Final Verification (Task 7)

- [ ] `pytest-cov` reports ≥80% line coverage across `biosphere/`
- [ ] `mypy --strict biosphere/` returns zero errors
- [ ] `ruff check biosphere/` returns zero errors
- [ ] All unit, integration, and benchmark tests pass
- [ ] VER-001 verification report created with results

## 5. Test Plan

| Test Type | What to Test | Expected Result |
|:----------|:------------|:----------------|
| Integration | `python -m biosphere train` for 100 steps | Completes without error, checkpoint saved |
| Integration | `python -m biosphere run` launch and quit | TUI opens and exits cleanly |
| Integration | Full pipeline: train → load checkpoint → run inference | Agent takes actions based on trained policy |
| Coverage | `pytest --cov=biosphere --cov-report=term-missing` | ≥80% line coverage |
| Static | `mypy --strict biosphere/` | Zero errors |
| Static | `ruff check biosphere/` | Zero errors |

## 6. Checkpoints

| Checkpoint | What Architect Reviews |
|:-----------|:----------------------|
| After `__main__.py` wiring | Dependency injection looks correct? |
| After train/run modes work | Both modes functional? |
| After coverage report | ≥80%? Any critical paths untested? |
| After VER-001 written | Governance audit complete? |
| Before merge | Ready for v1.0.0 tag? |

## 7. Risks & Open Questions

| Risk / Question | Mitigation / Answer |
|:----------------|:-------------------|
| No pre-trained checkpoint exists for `run` mode on first use | CLI should detect missing checkpoint and suggest `train` first |
| TUI main thread requirement vs training compute | Training runs in subprocess or completes before TUI launch |
| Coverage target 80% may require test backfill | Identify gaps during Sprint 1-2 test review |

## 8. Definition of Done

Sprint complete when:

1. `python -m biosphere` is a working application
2. All acceptance criteria met
3. VER-001 verification report created and passing
4. Branch `feat/EVO-003-cli-verification` merged to `master`
5. Git tag `v1.0.0` applied
