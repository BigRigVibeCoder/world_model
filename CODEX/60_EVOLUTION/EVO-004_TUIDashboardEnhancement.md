---
id: EVO-004
title: "Enhancement: Simulation Dashboard TUI"
type: reference
status: COMPLETE
owner: architect
agents: [coder, tester]
tags: [feature, ui, enhancement, tui]
related: [BLU-001, BLU-002, EVO-002, GOV-005]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** Upgrade the Textual TUI from a basic block-char grid + simple stats to a full simulation dashboard with colored dot organisms, titled panels, population bar charts, system metrics (tick, entropy, reward), and dark theme. Purely visual — no simulation logic changes.

# Enhancement Specification: Simulation Dashboard TUI

## 1. Overview

| Field | Value |
|:------|:------|
| **Priority** | P2 — Medium |
| **Status** | COMPLETE |
| **Requested By** | Architect |
| **Estimated Scope** | Small (4 files modified, 4 test fixtures updated) |
| **Depends On** | EVO-002 (TUI foundation) |

## 2. Problem Statement

The existing TUI uses block characters (`█`) with basic colors and a minimal stats panel. For colleague demos and UAT, the dashboard needs to look like a real ecological simulation monitor — matching the project's mockup image.

## 3. Changes

### 3.1 Modified Files

| File | Change |
|:-----|:-------|
| `biosphere/ui/payload.py` | Added `entropy`, `reward`, `paused` fields |
| `biosphere/ui/grid_widget.py` | Switched to colored dots (`●`/`·`), dark background, species-specific hex colors |
| `biosphere/ui/charts_widget.py` | Titled panel sections, bars scaled to max population, system metrics display |
| `biosphere/ui/app.py` | Dark theme CSS, bordered panels, species legend bar, entropy/reward computation, reset binding, 10 FPS |
| `tests/ui/test_app.py` | Updated 6 fixtures/assertions for new payload fields and dot chars |
| `tests/conftest.py` | Updated `RenderPayload` fixture with new fields |
| `tests/e2e/test_e2e.py` | Updated `RenderPayload` construction with new fields |

### 3.2 Visual Changes

| Before | After |
|:-------|:------|
| `█` block chars | `●` colored dots (green/yellow/red) |
| White background | Dark `#0a0a0a` background |
| No panel borders | Bordered panels with titles |
| No legend | Species legend bar at bottom |
| No entropy/reward display | Real-time entropy + reward metrics |
| 30 FPS (too fast to observe) | 10 FPS (watchable) |
| No reset | `r` key resets simulation |

## 4. Verification

- 195/195 tests pass
- Ruff clean, mypy --strict clean
- All existing test assertions updated for new char/field changes
