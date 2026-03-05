"""Build script for Biosphere C extensions.

Compiles biosphere/core/_phases_c.c into a shared library (.so/.pyd)
that accelerates the simulation engine's inner loops.

Usage:
    python setup.py build_ext --inplace

Refs: BLU-001 §4.3, GOV-003 §3.2
"""

from setuptools import Extension, setup

import numpy as np

phases_c_ext = Extension(
    name="biosphere.core._phases_c",
    sources=["biosphere/core/_phases_c.c"],
    include_dirs=[np.get_include()],
    extra_compile_args=["-O3", "-Wall", "-Wextra", "-std=c11"],
)

setup(
    name="biosphere-native",
    version="0.1.0",
    description="C extensions for Biosphere simulation engine",
    ext_modules=[phases_c_ext],
)
