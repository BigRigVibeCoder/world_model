"""Semantic type aliases per GOV-003 §6.1.

Provides domain-specific type aliases for improved code readability
and self-documenting parameter signatures. These are runtime-transparent
aliases (no overhead), but make intent clear at declaration sites.

Refs: GOV-003 §6.1, DEF-001-18
"""

from __future__ import annotations

# ── Simulation Domain Types ───────────────────────────────────────────────────

# Probabilities are always in [0.0, 1.0]
Probability = float

# Energy values representing organism metabolic state [0.0, 1.0]
Energy = float

# Health values representing organism vitality [0.0, 1.0]
Health = float

# Tick count — discrete simulation time steps
Tick = int

# Temperature in degrees Celsius
TemperatureCelsius = float

# Spatial grid coordinates (row, col)
GridCoord = tuple[int, int]

# Species identifier (uint8 value from state constants)
SpeciesId = int

# Intensity of an intervention [0.0, 1.0]
Intensity = float

# Growth rate for logistic resource model
GrowthRate = float

# Sigma for Gaussian blur diffusion
DiffusionSigma = float
