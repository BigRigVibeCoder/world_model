---
id: VER-002
title: "Test-to-Requirements Traceability Matrix"
type: reference
status: DRAFT
owner: architect
agents: [tester]
tags: [verification, testing, traceability, mc-dc]
related: [GOV-002, BLU-001, BLU-002, VER-001]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** Bidirectional traceability from test cases to requirements for the Biosphere project. Maps each test module to the specification sections it validates per GOV-002 §6.

# VER-002: Test-to-Requirements Traceability Matrix

## 1. Core Simulation (BLU-001)

| Requirement | Section | Test File | Test Class/Function |
|:------------|:--------|:----------|:-------------------|
| 50×50 Grid | BLU-001 §2.1 | test_state.py | TestGridState::test_grid_dimensions |
| Species Constants | BLU-001 §2.2 | test_state.py | TestSpeciesConstants |
| GridState TypedDict | BLU-001 §2.3 | test_state.py | TestGridState |
| 6-Phase Cycle | BLU-001 §4 | test_simulation.py | TestPhases |
| Weather Diffusion | BLU-001 §4.1 | test_simulation.py | TestPhases::test_weather_diffusion |
| Resource Growth | BLU-001 §4.2 | test_simulation.py | TestPhases::test_resource_growth |
| Movement | BLU-001 §4.3 | test_simulation.py | TestPhases::test_movement |
| Consumption | BLU-001 §4.4 | test_simulation.py | TestPhases::test_consumption |
| Reproduction | BLU-001 §4.5 | test_simulation.py | TestPhases::test_reproduction |
| Mortality | BLU-001 §4.6 | test_simulation.py | TestPhases::test_mortality |
| NaN Rollback | BLU-001 §5 | test_simulation.py | TestNanProtection |
| Param Validation | BLU-001 §3 | test_simulation.py | TestValidation |
| Interventions | BLU-001 §6 | test_simulation.py | TestInterventions |

## 2. RL Environment (BLU-002)

| Requirement | Section | Test File | Test Class/Function |
|:------------|:--------|:----------|:-------------------|
| Gymnasium API | BLU-002 §3 | test_environment.py | TestGymChecker |
| Observation Space | BLU-002 §3.1 | test_environment.py | TestObservation |
| Action Encoding | BLU-002 §3.5 | test_environment.py | TestActionMasking |
| Action Masking | BLU-002 §3.6 | test_environment.py | TestActionMasking |
| Reward Signal | BLU-002 §3.4 | test_reward.py | TestRewardComponents |
| MaskablePPO | BLU-002 §3 | test_training.py | TestTrainingPipeline |

## 3. Infrastructure (GOV-004, GOV-006)

| Requirement | Section | Test File | Test Class/Function |
|:------------|:--------|:----------|:-------------------|
| Structured Logging | GOV-006 §3 | test_logging.py | TestSetupLogging |
| Crash Artifacts | GOV-004 §4 | test_errors.py | TestCrashArtifact |
| Crash E2E Pipeline | GOV-004 §6 | test_crash_artifact.py | TestCrashArtifactPipeline |
| Error Categories | GOV-004 §2 | test_errors.py | TestErrorHierarchy |
| TRACE Logging | GOV-006 §14 | test_trace_logging.py | TestTraceLogging |
| LOG_LEVEL Override | GOV-006 §11 | test_trace_logging.py | test_trace_level_via_env_var |
| Config Loading | BLU-002 §4 | test_config.py | TestSimulationConfig |

## 4. E2E Integration

| Requirement | Section | Test File | Test Class/Function |
|:------------|:--------|:----------|:-------------------|
| Full Simulation E2E | BLU-001 §1 | test_e2e.py | TestE2ESimulation |
| RL Loop E2E | BLU-002 §1 | test_e2e.py | TestE2ERLLoop |
| Intervention E2E | BLU-001 §6 | test_e2e.py | TestE2EInterventions |
| TUI Rendering | EVO-002 §4.3 | test_e2e.py | TestE2ETUI |
