"""Transparent fallback wrapper for C-accelerated phase functions.

Attempts to import the compiled _phases_c extension module.
If unavailable (not compiled), exposes pure-Python fallback references
so that phases.py can use a single code path regardless.

Public API:
    HAS_C_EXTENSION      — bool, True if native module loaded
    c_phase_movement      — C function or None
    c_phase_spawn         — C function or None

DECISION: Transparent fallback pattern chosen over hard dependency.
ALTERNATIVES CONSIDERED: Mandatory C build (breaks pip install),
  runtime compilation via cffi (fragile, slow first import).
TRADEOFF: Graceful degradation at the cost of ~4× slower movement/reproduction
  when .so is missing. Users without GCC still get a working simulation.

FAILURE MODE: If the C extension segfaults, Python interpreter crashes.
BLAST RADIUS: Entire process terminates. RL training data may be lost.
MITIGATION:   Set HAS_C_EXTENSION = False at runtime to force Python fallback.
              All C functions are covered by the same test suite as Python.

REF: BLU-001 §4.3 (performance strategy)
REF: GOV-003 §3.2 (C/C++ coding standards)
SEE ALSO: _phases_c.c — the compiled C extension source
SEE ALSO: phases.py — consumer that checks HAS_C_EXTENSION before calling
"""

from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger(__name__)

# ── Attempt native import ─────────────────────────────────────────────────────

HAS_C_EXTENSION: bool = False
c_phase_movement: Any = None
c_phase_spawn: Any = None

try:
    from biosphere.core import _phases_c  # type: ignore[attr-defined]

    c_phase_movement = _phases_c.phase_movement_c
    c_phase_spawn = _phases_c.phase_spawn_offspring_c
    HAS_C_EXTENSION = True
    _logger.info(
        "C extension loaded: _phases_c (movement + reproduction accelerated)",
    )
except ImportError:
    _logger.debug(
        "C extension _phases_c not available — using pure Python fallback",
    )
