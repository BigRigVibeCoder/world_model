---
id: EVO-002
title: "Sprint 2: RL Environment, Training & TUI Dashboard"
type: reference
status: DRAFT
owner: architect
agents: [coder, tester]
tags: [feature, architecture, project-management]
related: [BLU-001, BLU-002, RUN-001, EVO-001, GOV-002, GOV-004]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** Second sprint for the Biosphere project. Builds the Gymnasium environment (BiosphereEnv), MaskablePPO RL training pipeline, and Textual TUI dashboard. Tasks 3-5 from RUN-001. Tasks 3→4 are sequential (RL depends on Gym env); Task 5 (TUI) can run in parallel with RL since both depend only on Sprint 1's core engine.

# Feature Specification: Sprint 2 — RL Environment, Training & TUI

## 1. Overview

| Field | Value |
|:------|:------|
| **Priority** | P1 — High |
| **Status** | DRAFT |
| **Requested By** | Architect |
| **Branch** | `feat/EVO-002-rl-tui` |
| **Estimated Scope** | Large (8+ files) |
| **Backlog Tasks** | RUN-001 Tasks 3, 4, 5 |
| **Depends On** | EVO-001 (Sprint 1 must be merged) |

## 2. Problem Statement

Sprint 1 delivers the simulation engine but no way to train an RL agent or visualize the world. This sprint adds:

1. **Gymnasium wrapper** — Translates core state ↔ RL tensors via the RL Codec API
2. **MaskablePPO training** — Trains the Caretaker agent with action masking
3. **Textual TUI** — Renders the world grid and population charts in real-time

Tasks 3→4 are sequential. Task 5 (TUI) can be developed in parallel.

## 3. Proposed Solution

### 3.1 Files to Create or Modify

| Action | File | Purpose |
|:-------|:-----|:--------|
| CREATE | `biosphere/rl/environment.py` | BiosphereEnv(gym.Env), action encoding, observation builder, action masks |
| CREATE | `biosphere/rl/reward.py` | Multi-objective reward (Shannon entropy, stability, population health) |
| CREATE | `biosphere/rl/train.py` | MaskablePPO training loop with checkpointing |
| MODIFY | `biosphere/rl/__init__.py` | Export BiosphereEnv, ActionDecodingError |
| CREATE | `biosphere/ui/app.py` | BiosphereApp main Textual application |
| CREATE | `biosphere/ui/grid_widget.py` | GridWidget for emoji/color grid rendering |
| CREATE | `biosphere/ui/charts_widget.py` | ChartsWidget for population bar charts |
| CREATE | `biosphere/ui/payload.py` | RenderPayload data class for UI snapshots |
| MODIFY | `biosphere/ui/__init__.py` | Export BiosphereApp, RenderPayload |
| CREATE | `config/training.yaml` | MaskablePPO hyperparameters |
| CREATE | `tests/rl/test_environment.py` | Gym env checker, observation/action space tests |
| CREATE | `tests/rl/test_reward.py` | Reward function monotonicity tests |
| CREATE | `tests/ui/test_app.py` | TUI smoke tests |

### 3.2 Dependencies

| Dependency | Required For | Version |
|:-----------|:------------|:--------|
| `gymnasium` | Env protocol | ≥0.29 |
| `sb3-contrib` | MaskablePPO | ≥2.0 |
| `stable-baselines3` | Base RL framework | ≥2.0 |
| `textual` | TUI framework | ≥0.40 |
| **EVO-001 merged** | Core engine, GridState, infrastructure | — |

## 4. Acceptance Criteria

### 4.1 Gymnasium Environment (Task 3)

- [ ] `gymnasium.utils.env_checker.check_env()` passes without warnings
- [ ] `BiosphereEnv.action_masks()` returns `np.ndarray` of shape `(37,)`, dtype `bool`
- [ ] `BiosphereEnv.build_observation()` (static) matches observation_space
- [ ] `BiosphereEnv.decode_action()` (static) returns valid `Intervention`
- [ ] `BiosphereEnv.compute_action_masks()` (static) masks extinct species
- [ ] Reward function returns higher values for higher Shannon entropy
- [ ] Terminal condition: all non-plant species extinct → `terminated=True`

### 4.2 RL Training (Task 4)

- [ ] Training starts and completes 1000 timesteps without errors
- [ ] Action masking prevents invalid actions (culling extinct species)
- [ ] Agent checkpoints saved to disk with unique correlation ID (GOV-006)
- [ ] `config/training.yaml` configures all MaskablePPO hyperparameters

### 4.3 Textual TUI (Task 5)

- [ ] TUI displays 50×50 grid with emoji/color species rendering
- [ ] Population bar charts update in real-time during simulation
- [ ] TUI achieves 30 FPS without flicker
- [ ] `RenderPayload` data class carries grid snapshot + stats to UI

## 5. Test Plan

| Test Type | What to Test | Expected Result |
|:----------|:------------|:----------------|
| Unit | `check_env()` on BiosphereEnv | Zero warnings |
| Unit | Action encoding round-trip | encode → decode → same intervention |
| Unit | Action masks with extinct species | Correct species dimensions masked |
| Unit | Reward monotonicity | Higher entropy → higher reward |
| Integration | 1000-step training run | No crashes, checkpoint saved |
| Unit | GridWidget rendering | Correct emoji mapping for each species |
| Smoke | TUI launch and quit | App starts and exits cleanly |

## 6. Checkpoints

| Checkpoint | What Architect Reviews |
|:-----------|:----------------------|
| After `BiosphereEnv` passes `check_env()` | Observation/action spaces correct? |
| After reward function | Incentive structure makes ecological sense? |
| After 1000-step training | Agent learning? Masking working? |
| After TUI renders grid | Visual quality acceptable? |
| Before merge | All 3 tasks integrated, tests passing? |

## 7. Risks & Open Questions

| Risk / Question | Mitigation / Answer |
|:----------------|:-------------------|
| MaskablePPO MultiDiscrete masking format | BLU-002 §3.2 specifies flat `(37,)` array; verify against sb3-contrib docs |
| Textual 30 FPS target with 50×50 grid | Profile rendering; consider batched updates if needed |
| Training convergence in 1000 steps unlikely | 1000 steps is the smoke test; real training happens outside sprint scope |

## 8. Definition of Done

Sprint complete when all acceptance criteria met, tests pass, `mypy --strict` clean, and branch `feat/EVO-002-rl-tui` merged to `master`.
