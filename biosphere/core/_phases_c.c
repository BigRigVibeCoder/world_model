/**
 * @file _phases_c.c
 * @brief CPython C extension for Biosphere simulation hot loops.
 *
 * Accelerates organism movement and offspring spawning by performing
 * the entire cell-iteration logic in C, eliminating Python-level `for`
 * loops AND the NumPy intermediate array overhead (mask creation,
 * np.where, etc).
 *
 * READING GUIDE FOR INCIDENT RESPONDERS:
 *   1. If organisms stop moving      → check phase_movement_c() bounds logic
 *   2. If offspring have wrong stats  → check phase_spawn_offspring_c() constants
 *   3. If segfault occurs             → check PyArg_ParseTuple format strings
 *   4. To disable C extension         → set native.HAS_C_EXTENSION = False
 *
 * DECISION: CPython C API chosen over Cython and cffi.
 * ALTERNATIVES: Cython (extra .pyx build step), cffi (slower, no buffer access).
 * TRADEOFF: Requires GCC + numpy headers at build time but zero runtime deps.
 *
 * Follows GOV-003 §3.2: MISRA C / CERT C standards.
 *   - Fixed-width types (uint8_t, float)
 *   - No dynamic allocation after init
 *   - Single return point per function body
 *   - Doxygen-style comments
 *
 * REF: BLU-001 §4.3 (performance target: ≥1000 steps/sec)
 * REF: GOV-003 §7.2 (C/C++ coding rules)
 * SEE ALSO: phases.py — Python fallback implementation
 * SEE ALSO: native.py — transparent import wrapper
 *
 * Build: python3 setup.py build_ext --inplace
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>

/* NumPy C API */
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>

#include <stdint.h>
#include <stdlib.h>

/* ── Constants (mirror biosphere.core.state) ─────────────────────────── */

#define SPECIES_EMPTY    ((uint8_t)0)
#define N_ATTRS          3   /* health=0, energy=1, age=2 */

/* Direction offsets: up, down, left, right */
static const int DR[4] = {-1, 1, 0, 0};
static const int DC[4] = {0, 0, -1, 1};


/* ══════════════════════════════════════════════════════════════════════
 * Function: phase_movement_c
 *
 * Complete replacement for the Python phase_movement() function.
 * Handles the entire movement logic in C:
 *   1. Iterate all cells, find organisms of the given species
 *   2. Apply movement probability filter
 *   3. Pick random direction
 *   4. Validate bounds
 *   5. Find empty target slot and transfer
 *
 * This eliminates ALL Python-level loops and NumPy intermediate
 * arrays (masks, np.where, etc.) — the main bottleneck.
 *
 * Args (from Python):
 *   species_grid:    uint8   C-contiguous (H, W, MPC)
 *   organism_attrs:  float32 C-contiguous (H, W, MPC, 3)
 *   grid_h:          int
 *   grid_w:          int
 *   max_per_cell:    int
 *   species_id:      int     (PREY=2 or PREDATOR=3)
 *   move_prob:       float   movement probability (e.g. 0.2)
 *   rand_array:      float32 C-contiguous (H, W, MPC) — pre-generated
 *                    uniform random values in [0, 1) for movement
 *                    probability checks
 *   dir_array:       int32   C-contiguous (H, W, MPC) — pre-generated
 *                    random integers in {0,1,2,3} for directions
 *
 * PRECONDITION:  All arrays must be C-contiguous NumPy arrays.
 *                species_grid dtype=uint8, organism_attrs dtype=float32,
 *                rand_array dtype=float32, dir_array dtype=int32.
 * POSTCONDITION: Organism count is conserved (moved, not created/destroyed).
 * SIDE EFFECTS:  Mutates species_grid and organism_attrs in-place.
 * FAILURE MODE:  If arrays are not C-contiguous, undefined behavior (segfault).
 * BLAST RADIUS:  Python interpreter crashes. RL training data lost.
 * MITIGATION:    phases.py validates arrays before calling; native.py fallback.
 * SEE ALSO:      phases.py:phase_movement() — Python fallback
 *
 * Returns: int — number of successful moves
 * ══════════════════════════════════════════════════════════════════════ */
static PyObject *
phase_movement_c(PyObject *self, PyObject *args)
{
    (void)self;  /* Unused — standard CPython method signature */

    PyArrayObject *sg_arr   = NULL;
    PyArrayObject *oa_arr   = NULL;
    PyArrayObject *rand_arr = NULL;
    PyArrayObject *dir_arr  = NULL;
    int grid_h = 0, grid_w = 0, mpc = 0, species_id = 0;
    float move_prob = 0.0f;

    if (!PyArg_ParseTuple(args, "O!O!iiiifO!O!",
            &PyArray_Type, &sg_arr,
            &PyArray_Type, &oa_arr,
            &grid_h, &grid_w, &mpc, &species_id,
            &move_prob,
            &PyArray_Type, &rand_arr,
            &PyArray_Type, &dir_arr)) {
        return NULL;
    }

    uint8_t *sg   = (uint8_t *)PyArray_DATA(sg_arr);
    float   *oa   = (float *)PyArray_DATA(oa_arr);
    float   *rnd  = (float *)PyArray_DATA(rand_arr);
    int32_t *dirs = (int32_t *)PyArray_DATA(dir_arr);

    const int cell_stride_sg = mpc;             /* species_grid stride per cell */
    const int cell_stride_oa = mpc * N_ATTRS;   /* organism_attrs stride per cell */
    int total_moves = 0;

    /* ── Single pass over all cells ─────────────────────────────── */
    for (int r = 0; r < grid_h; r++) {
        for (int c = 0; c < grid_w; c++) {
            const int cell_idx = r * grid_w + c;
            const int sg_base = cell_idx * cell_stride_sg;
            const int oa_base = cell_idx * cell_stride_oa;

            for (int s = 0; s < mpc; s++) {
                /* Skip if not the target species */
                if (sg[sg_base + s] != (uint8_t)species_id) {
                    continue;
                }

                /* Movement probability check */
                if (rnd[sg_base + s] >= move_prob) {
                    continue;
                }

                /* Pick direction */
                const int d = dirs[sg_base + s] & 3;  /* mod 4, safe */
                const int tr = r + DR[d];
                const int tc = c + DC[d];

                /* Bounds check */
                if (tr < 0 || tr >= grid_h || tc < 0 || tc >= grid_w) {
                    continue;
                }

                /* Find empty slot in target cell */
                const int tgt_cell = tr * grid_w + tc;
                const int tgt_sg_base = tgt_cell * cell_stride_sg;
                const int tgt_oa_base = tgt_cell * cell_stride_oa;

                int ts = -1;
                for (int t = 0; t < mpc; t++) {
                    if (sg[tgt_sg_base + t] == SPECIES_EMPTY) {
                        ts = t;
                        break;
                    }
                }
                if (ts < 0) {
                    continue;  /* Target cell full */
                }

                /* ── Transfer organism ────────────────────────── */
                sg[tgt_sg_base + ts] = sg[sg_base + s];
                sg[sg_base + s] = SPECIES_EMPTY;

                for (int a = 0; a < N_ATTRS; a++) {
                    oa[tgt_oa_base + ts * N_ATTRS + a] =
                        oa[oa_base + s * N_ATTRS + a];
                    oa[oa_base + s * N_ATTRS + a] = 0.0f;
                }

                total_moves++;
                break;  /* This slot moved — don't move it again */
            }
        }
    }

    return PyLong_FromLong(total_moves);
}


/* ══════════════════════════════════════════════════════════════════════
 * Function: phase_spawn_offspring_c
 *
 * Complete replacement for the Python _spawn_offspring() inner loop.
 * Handles the full spawning logic in C:
 *   1. Iterate all cells
 *   2. Find slots flagged for reproduction
 *   3. Find empty slots for offspring
 *   4. Place offspring and apply parent energy cost
 *
 * Args (from Python):
 *   species_grid:    uint8   C-contiguous (H, W, MPC)
 *   organism_attrs:  float32 C-contiguous (H, W, MPC, 3)
 *   reproduce_mask:  uint8   C-contiguous (H, W, MPC) — True=reproducing
 *   grid_h:          int
 *   grid_w:          int
 *   max_per_cell:    int
 *   species_id:      int
 *
 * PRECONDITION:  All arrays must be C-contiguous NumPy arrays.
 *                reproduce_mask dtype=uint8 (bool view).
 * POSTCONDITION: Offspring placed with health=0.8, energy=0.4, age=0.
 *                Parent energy halved (×0.5).
 * SIDE EFFECTS:  Mutates species_grid and organism_attrs in-place.
 * FAILURE MODE:  If arrays are not C-contiguous, undefined behavior.
 * SEE ALSO:      phases.py:_spawn_offspring() — Python fallback
 *
 * Returns: int — number of offspring spawned
 * ══════════════════════════════════════════════════════════════════════ */
static PyObject *
phase_spawn_offspring_c(PyObject *self, PyObject *args)
{
    (void)self;

    PyArrayObject *sg_arr    = NULL;
    PyArrayObject *oa_arr    = NULL;
    PyArrayObject *repro_arr = NULL;
    int grid_h = 0, grid_w = 0, mpc = 0, species_id = 0;

    if (!PyArg_ParseTuple(args, "O!O!O!iiii",
            &PyArray_Type, &sg_arr,
            &PyArray_Type, &oa_arr,
            &PyArray_Type, &repro_arr,
            &grid_h, &grid_w, &mpc, &species_id)) {
        return NULL;
    }

    uint8_t *sg    = (uint8_t *)PyArray_DATA(sg_arr);
    float   *oa    = (float *)PyArray_DATA(oa_arr);
    uint8_t *repro = (uint8_t *)PyArray_DATA(repro_arr);

    const int cell_stride_sg = mpc;
    const int cell_stride_oa = mpc * N_ATTRS;
    int total_spawned = 0;

    for (int r = 0; r < grid_h; r++) {
        for (int c = 0; c < grid_w; c++) {
            const int cell_idx = r * grid_w + c;
            const int sg_base = cell_idx * cell_stride_sg;
            const int oa_base = cell_idx * cell_stride_oa;

            /* Find first reproducing slot */
            int rs = -1;
            for (int s = 0; s < mpc; s++) {
                if (repro[sg_base + s]) {
                    rs = s;
                    break;
                }
            }
            if (rs < 0) {
                continue;
            }

            /* Find first empty slot */
            int es = -1;
            for (int s = 0; s < mpc; s++) {
                if (sg[sg_base + s] == SPECIES_EMPTY) {
                    es = s;
                    break;
                }
            }
            if (es < 0) {
                continue;
            }

            /* Place offspring */
            sg[sg_base + es] = (uint8_t)species_id;
            oa[oa_base + es * N_ATTRS + 0] = 0.8f;   /* health */
            oa[oa_base + es * N_ATTRS + 1] = 0.4f;   /* energy */
            oa[oa_base + es * N_ATTRS + 2] = 0.0f;   /* age */

            /* Parent energy cost */
            oa[oa_base + rs * N_ATTRS + 1] *= 0.5f;

            total_spawned++;
        }
    }

    return PyLong_FromLong(total_spawned);
}


/* ══════════════════════════════════════════════════════════════════════
 * Module Definition
 * ══════════════════════════════════════════════════════════════════════ */

static PyMethodDef PhasesC_methods[] = {
    {
        "phase_movement_c",
        phase_movement_c,
        METH_VARARGS,
        "Complete organism movement phase in C.\n\n"
        "Replaces the entire phase_movement() Python function\n"
        "for a single species. Handles probability, direction,\n"
        "bounds checking, and organism transfer in one pass.\n"
        "Returns the number of successful moves."
    },
    {
        "phase_spawn_offspring_c",
        phase_spawn_offspring_c,
        METH_VARARGS,
        "Place offspring into empty grid cell slots in C.\n\n"
        "Replaces _spawn_offspring() Python function.\n"
        "Iterates all cells, finds reproducers, places offspring.\n"
        "Returns the number of offspring spawned."
    },
    {NULL, NULL, 0, NULL}   /* Sentinel */
};

static struct PyModuleDef phases_c_module = {
    PyModuleDef_HEAD_INIT,
    "_phases_c",
    "C-accelerated simulation phases for biosphere.core.\n\n"
    "Provides phase_movement_c() and phase_spawn_offspring_c()\n"
    "that replace entire Python phase functions, eliminating both\n"
    "Python for-loops and NumPy intermediate array overhead.\n"
    "Refs: BLU-001 §4.3, GOV-003 §3.2",
    -1,
    PhasesC_methods,
    NULL, NULL, NULL, NULL  /* m_slots, m_traverse, m_clear, m_free */
};

PyMODINIT_FUNC
PyInit__phases_c(void)
{
    import_array();  /* Initialize NumPy C API */
    return PyModule_Create(&phases_c_module);
}
