---
id: DEF-002
title: "GOV-003 v2.1.0 Incident-Readability Gap Analysis"
type: defect
status: RESOLVED
owner: architect
agents: [all]
tags: [defect, governance, compliance, GOV-003, readability, incident]
related: [GOV-003, BLU-001, DEF-001]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** Gap analysis of all biosphere core files against GOV-003 v2.1.0 §1.4 (Incident-Readability Enhancements). 14 findings across 5 files. Zero of the new §1.4 annotation types — Decision Records, Reading Guides, Contract Comments, Failure Mode annotations, Cross-Reference anchors — are present in any production code. Immediate remediation required.

# DEF-002: GOV-003 v2.1.0 Incident-Readability Gap Analysis

## 1. Audit Context

| Field | Value |
|:------|:------|
| Standard | GOV-003 v2.1.0 (§1.4.1–§1.4.5) |
| Files Audited | 5 (`simulation.py`, `phases.py`, `_phases_c.c`, `native.py`, `state.py`) |
| Tests | 66/66 pass |
| Static | `ruff check` ✅ |

---

## 2. P0 — Critical (Must Fix)

### 2.1 DEF-002-01: Missing Reading Guides / Panic Breadcrumbs
**Ref:** GOV-003 §1.4.2

Both `phases.py` (504 lines, 13+ public functions) and `simulation.py` (412 lines, 10+ methods) qualify as complex modules (≥3 public functions, ≥150 lines). Neither has a Reading Guide for incident responders.

**Affected files:** `phases.py`, `simulation.py`

---

### 2.2 DEF-002-02: Zero Decision Record Comments
**Ref:** GOV-003 §1.4.1

Multiple non-trivial design choices have zero inline ADR documentation:
- C extension vs Numba JIT vs Cython (`_phases_c.c`, `phases.py`)
- Transparent fallback pattern (`native.py`)
- In-place mutation vs copy-on-write (`phases.py`)
- NumPy vectorization vs per-entity loops (`phases.py`)
- NaN rollback with energy dampening (`simulation.py`)

**Affected files:** `_phases_c.c`, `native.py`, `phases.py`, `simulation.py`

---

### 2.3 DEF-002-03: Zero Contract Comments
**Ref:** GOV-003 §1.4.3

Functions with preconditions, side effects, or thread constraints lack contract annotations:

| Function | File | Missing |
|:---------|:-----|:--------|
| `phase_movement()` | phases.py | SIDE EFFECTS (mutates state in-place) |
| `_spawn_offspring()` | phases.py | PRECONDITION (reproduce mask must be bool), SIDE EFFECTS |
| `phase_movement_c()` | _phases_c.c | PRECONDITION (arrays must be C-contiguous), SIDE EFFECTS |
| `phase_spawn_offspring_c()` | _phases_c.c | PRECONDITION (arrays must be C-contiguous), SIDE EFFECTS |
| `SimulationEngine.step()` | simulation.py | THREAD SAFETY (not thread-safe) |
| `SimulationEngine.__init__()` | simulation.py | SIDE EFFECTS (initializes RNG, allocates state) |

---

## 3. P1 — High

### 3.1 DEF-002-04: Zero Failure Mode Annotations
**Ref:** GOV-003 §1.4.4

Critical functions with downstream impact lack failure-mode documentation:

| Function | Blast Radius |
|:---------|:-------------|
| `phase_movement()` | Organisms frozen; ecosystem diverges |
| `SimulationEngine.step()` | RL agent sees stale state; TUI displays incorrect world |
| `_check_nan_rollback()` | Raises on double-NaN; kills simulation |
| C extension import failure | Falls back silently; performance degradation |

---

### 3.2 DEF-002-05: Zero Cross-Reference Anchors
**Ref:** GOV-003 §1.4.5

None of the audited files use `REF:` or `SEE ALSO:` prefixes for machine-parseable cross-referencing, despite many spec/sibling relationships:

| Relationship | Missing Anchor |
|:-------------|:---------------|
| `phases.py` ↔ `_phases_c.c` | SEE ALSO between C and Python implementations |
| `phases.py` → BLU-001 §4 | REF to blueprint spec |
| `native.py` → `_phases_c.c` | SEE ALSO to compiled module |
| `simulation.py` → GOV-004 | REF for error handling pattern |
| `_phases_c.c` → GOV-003 §7.2 | REF to C standards |

---

## 4. Remediation Plan

All findings will be fixed by adding the required annotations directly to the source files:

| ID | Fix | File(s) |
|:---|:----|:--------|
| DEF-002-01 | Add READING GUIDE docstring block | `phases.py`, `simulation.py` |
| DEF-002-02 | Add DECISION / ALTERNATIVES / TRADEOFF comments | `phases.py`, `_phases_c.c`, `native.py`, `simulation.py` |
| DEF-002-03 | Add PRECONDITION / POSTCONDITION / SIDE EFFECTS / THREAD SAFETY | `phases.py`, `_phases_c.c`, `simulation.py` |
| DEF-002-04 | Add FAILURE MODE / BLAST RADIUS / MITIGATION annotations | `phases.py`, `simulation.py`, `native.py` |
| DEF-002-05 | Add REF: / SEE ALSO: cross-reference anchors | All 5 files |
