---
id: DEF-001
title: "Governance Compliance Gap Analysis"
type: reference
status: REVIEW
owner: architect
agents: [all]
tags: [defect, governance, compliance, audit, sprint]
related: [GOV-001, GOV-002, GOV-003, GOV-004, GOV-005, GOV-006]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** Systematic audit of biosphere codebase against all 6 governance documents. 22 gaps found: 3 Critical (assertion density, file length, function length), 5 High (ruff profile, MANIFEST, CI tools, MC/DC, test artifacts), 8 Medium, 6 Low. Sprint 3 addresses all P0 and P1 items. No security or data-loss issues.

# DEF-001: Governance Compliance Gap Analysis

## 1. Audit Context

| Field | Value |
|:------|:------|
| Branch | `master` (post-merge EVO-001 + EVO-002) |
| Commit | `04591af` |
| Tests | 177/177 pass, 84% coverage |
| Static | `ruff check` ✅, `mypy --strict` ✅ |

---

## 2. P0 — Critical

### 2.1 DEF-001-01: Zero Assertion Density
**Ref:** GOV-003 §2 Rule 5, §11

All non-trivial production functions have **zero** `assert` statements. Mandate: ≥2 per function >10 lines.

**Affected files:** `simulation.py`, `environment.py`, `train.py`, `config.py`, `reward.py`

**Fix:** Add precondition/postcondition/invariant assertions to all non-trivial functions.

---

### 2.2 DEF-001-02: `simulation.py` at 775 Lines
**Ref:** GOV-003 §4.1

Limit: ≤300 target, ≤500 absolute max. Currently **775 lines** (155% over).

**Fix:** Extract 6 phase methods into `biosphere/core/phases.py`.

---

### 2.3 DEF-001-03: 6 Functions Over 60-Line Limit
**Ref:** GOV-003 §4.1, §2 Rule 4

| Function | File | Lines |
|:---------|:-----|:------|
| `_initialize_state()` | simulation.py | 99 |
| `setup_logging()` | logging.py | 95 |
| `_phase_consumption()` | simulation.py | 80 |
| `train()` | train.py | 76 |
| `_phase_movement()` | simulation.py | 69 |
| `compute_reward()` | reward.py | 63 |

**Fix:** Split each into smaller helper functions.

---

## 3. P1 — High

### 3.1 DEF-001-04: Ruff Profile Not GOV-003 Compliant
**Ref:** GOV-003 §12.1

Running `ruff --select ALL` produces 64 errors. Project does not use the mandatory profile.

**Fix:** Adopt GOV-003 ruff profile, fix/suppress findings.

---

### 3.2 DEF-001-05: MANIFEST.yaml References Template
**Ref:** GOV-001 §5

Still says `project: "agentic-architect-template"`. Missing biosphere document entries.

**Fix:** Update project name and add all document entries.

---

### 3.3 DEF-001-06: Missing `radon` and `bandit` CI Tools
**Ref:** GOV-003 §6.5

Neither installed nor in `pyproject.toml` dev deps.

**Fix:** Add to dev dependencies, configure CI checks.

---

### 3.4 DEF-001-07: No MC/DC Coverage Enforcement
**Ref:** GOV-002 §6

No MC/DC tooling. No traceability matrix from tests → requirements.

**Fix:** Document MC/DC for critical paths; create traceability matrix.

---

### 3.5 DEF-001-08: No Test Artifacts Committed
**Ref:** GOV-002 §17

Coverage reports generated to stdout only. No reports in `40_VERIFICATION/`.

**Fix:** Generate and commit HTML/XML coverage reports.

---

## 4. P2 — Medium

| ID | Finding | Ref |
|:---|:--------|:----|
| DEF-001-09 | No mutation testing configured | GOV-002 §7 |
| DEF-001-10 | Stale feature branches not deleted | GOV-005 §7.1 |
| DEF-001-11 | `@trace_execution` not applied to any function | GOV-006 §5.3 |
| DEF-001-12 | `set_correlation_id()` never called | GOV-006 §4/GOV-004 §8 |
| DEF-001-13 | `setup_logging()` never called at app entry | GOV-006 §5.1 |
| DEF-001-14 | No `LOG_LEVEL=TRACE` test | GOV-006 §14 |
| DEF-001-15 | No error chaining (`raise X from original`) | GOV-004 §3 |
| DEF-001-16 | No crash artifact recovery E2E test | GOV-004 §6 |

---

## 5. P3 — Low

| ID | Finding | Ref |
|:---|:--------|:----|
| DEF-001-17 | `wrapper()` missing docstring | GOV-003 §1.2 |
| DEF-001-18 | No semantic type aliases | GOV-003 §6.1 |
| DEF-001-19 | `pyproject.toml` project name check | GOV-001 §5 |
| DEF-001-20 | No docs in `40_VERIFICATION/` | GOV-001/GOV-002 §17 |
| DEF-001-21 | This DEF-001 is the first defect doc → ✅ | GOV-001 §1 |
| DEF-001-22 | Missing bidirectional `related` cross-refs | GOV-001 §10.2 |
