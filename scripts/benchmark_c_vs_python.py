#!/usr/bin/env python3
"""Benchmark: C extension vs pure Python simulation performance.

Runs 500 simulation steps with both backends and reports
the throughput difference (ops/sec).

Usage: python3 scripts/benchmark_c_vs_python.py
Refs: BLU-001 §4.3, GOV-002 §13
"""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace

# Suppress ALL logging (stdlib + structlog) to measure pure computation.
# structlog's per-step debug logging adds ~3-5ms/step overhead that
# dominates wall-clock time and completely masks the C extension speedup.
logging.disable(logging.CRITICAL)

import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
)

from biosphere.core import native
from biosphere.core.simulation import SimulationEngine


def make_params() -> SimpleNamespace:
    """Create default simulation parameters."""
    return SimpleNamespace(
        growth_rate=0.1,
        reproduction_threshold=0.6,
        max_age_prey=500,
        max_age_predator=300,
        metabolic_rate=0.02,
        weather_sigma=2.0,
    )


def benchmark_steps(n_steps: int, label: str) -> float:
    """Run n_steps and return ops/sec."""
    engine = SimulationEngine(make_params())
    # Warm-up: 10 steps
    for _ in range(10):
        engine.step()

    t0 = time.perf_counter()
    for _ in range(n_steps):
        engine.step()
    elapsed = time.perf_counter() - t0

    ops = n_steps / elapsed
    print(f"  {label}: {n_steps} steps in {elapsed:.3f}s → {ops:.1f} ops/sec")
    return ops


def main() -> None:
    """Run comparative benchmark."""
    n_steps = 500

    print("=" * 64)
    print("Biosphere Simulation Engine — C Extension Benchmark")
    print("=" * 64)
    print()

    # Phase 1: Benchmark with C extension (if available)
    c_ops = 0.0
    if native.HAS_C_EXTENSION:
        print("[1/2] C Extension ENABLED:")
        c_ops = benchmark_steps(n_steps, "C-accelerated")
    else:
        print("[1/2] C Extension NOT AVAILABLE — skipping")

    # Phase 2: Force pure Python fallback
    orig_flag = native.HAS_C_EXTENSION
    native.HAS_C_EXTENSION = False
    print("[2/2] Pure Python (forced fallback):")
    py_ops = benchmark_steps(n_steps, "Pure Python")
    native.HAS_C_EXTENSION = orig_flag  # restore

    # Summary
    print()
    print("-" * 64)
    if c_ops > 0:
        speedup = c_ops / py_ops
        print(f"  Speedup: {speedup:.2f}× (C: {c_ops:.1f} vs Python: {py_ops:.1f} ops/sec)")
    else:
        print(f"  Pure Python baseline: {py_ops:.1f} ops/sec")
    print("-" * 64)


if __name__ == "__main__":
    main()
