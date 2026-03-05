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
    # WHY -Wno-error=pedantic: NumPy's C API headers contain ISO C function
    # pointer casts that trigger pedantic warnings. These are standard practice
    # in CPython extensions and not defects in our code. We still emit pedantic
    # warnings (-Wpedantic) for visibility but don't promote them to errors.
    # REF: GOV-003 §7.4 (gcc -Wall -Wextra -Werror -pedantic)
    extra_compile_args=[
        "-O3", "-Wall", "-Wextra", "-Werror",
        "-Wpedantic", "-Wno-error=pedantic",
        "-std=c11",
    ],
)

setup(
    name="biosphere-native",
    version="0.1.0",
    description="C extensions for Biosphere simulation engine",
    ext_modules=[phases_c_ext],
)
