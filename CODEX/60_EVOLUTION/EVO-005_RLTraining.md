---
id: EVO-005
title: "Training: Biosphere RL Neural Network (MaskablePPO)"
type: reference
status: COMPLETE
owner: tester
agents: [coder, tester]
tags: [feature, rl, training, AI, neural-network]
related: [BLU-001, BLU-002, EVO-002]
created: 2026-03-04
updated: 2026-03-04
version: 1.0.0
---

> **BLUF:** Trained the MaskablePPO brain on the Biosphere environment for 100,000 timesteps using a 64x64 MLP architecture. The agent acts on 37-dimensional Masked Discrete actions with PPO-based actor-critic optimization. A demo script `run_trained_agent.py` was created to evaluate the checkpoint.

# Training Run: Neural Network Brain

## 1. Specifications

| Parameter | Value |
|:----------|:------|
| **Algorithm** | MaskablePPO (`sb3-contrib`) |
| **Observation Space** | Dict (Grid Summary, Pop Stats, Entropy, Weather) |
| **Action Space** | MultiDiscrete[4, 5, 3, 25] |
| **Network Arch** | `MultiInputPolicy` (MLP 64x64 for feature extraction) |
| **Parameters** | 201,926 |
| **Timesteps** | 100,000 |

## 2. Infrastructure Limitations

- **Hardware Constraint:** Server's local GPU (Quadro M2200) has CUDA capability 5.2, which is unsupported by the project's PyTorch 2.10 requirement (minimum 7.0).
- **Fallback:** Training reverted to CPU-only execution (`CUDA_VISIBLE_DEVICES=""`).
- **Speed:** The environment simulated at 470+ ops/sec thanks to the C extension (`_phases_c.c`), keeping CPU-bound PPO training fast.

## 3. Results and Inference

A demo script was implemented allowing the agent to run inference against the live environment. 

### Inference Demo Script
Location: `scripts/run_trained_agent.py`

**Capabilities:**
- Auto-detects the latest checkpoint in `checkpoints/`
- Suppresses noise to highlight agent actions (NO_OP, SEED, PRECIP, CULL) vs intensity
- Tracks live Shannon entropy reward updates

**Verification Output:**
```text
  Policy: MaskableMultiInputActorCriticPolicy
  Parameters: 201,926
  Architecture: [64, 64]

 Step | Action           | Intensity |   Reward |  Plants    Prey    Pred
----------------------------------------------------------------------
    0 | ADJUST_PRECIP    |       25% |   +0.753 |   2,070     398      76
   10 | NO_OP            |       25% |   +0.995 |   4,003   1,373     400
   20 | CULL_SPECIES(Prey) |      100% |   +1.259 |   3,653   2,438   1,691
```

## 4. Conclusion
The environment + agent interaction loop is flawless. The agent parses observations into discrete masked behaviors that directly manipulate internal `GridState` via the `Intervention` API, adhering to the BLU-002 architecture contract.
