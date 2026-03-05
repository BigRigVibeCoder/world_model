/**
 * @file _phases_c.c
 * @brief CPython C extension for Biosphere simulation hot loops.
 *
 * Accelerates organism movement and offspring spawning by performing
 * the entire cell-iteration logic in C, eliminating Python-level `for`
 * loops AND the NumPy intermediate array overhead (mask creation,
 * np.where, etc).
 *
 * COMPLIANCE: GOV-003 v2.2.0 (Coding Standard)
 * REVIEWED:   2026-03-04 — structured for independent code review per §10.1
 *
 * READING GUIDE FOR INCIDENT RESPONDERS:
 *   1. If organisms stop moving      → check phase_movement_c() bounds logic
 *   2. If offspring have wrong stats  → check OFFSPRING_* constants below
 *   3. If segfault occurs             → check PyArg_ParseTuple format strings
 *   4. To disable C extension         → set native.HAS_C_EXTENSION = False
 *
 * DECISION: CPython C API chosen over Cython and cffi.
 * ALTERNATIVES: Cython (extra .pyx build step), cffi (slower, no buffer access).
 * TRADEOFF: Requires GCC + numpy headers at build time but zero runtime deps.
 *
 * Follows GOV-003 §7.2: MISRA C / CERT C standards.
 *   - Fixed-width types (uint8_t, int32_t, float)
 *   - No dynamic allocation in hot loops (calloc once at init, free before return)
 *   - Doxygen-style comments
 *   - All variables initialized at declaration
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

#include <assert.h>
#include <stdint.h>
#include <stdlib.h>


/* ══════════════════════════════════════════════════════════════════════
 * Constants (mirror biosphere.core.state and biosphere.core.phases)
 *
 * WHY: GOV-003 §5.3 mandates all numeric literals be named constants.
 * Every value here has a corresponding Python-side constant to ensure
 * parity between the C hot path and the Python fallback.
 * ══════════════════════════════════════════════════════════════════════ */

/** Species grid sentinel: slot is unoccupied. */
#define SPECIES_EMPTY           ((uint8_t)0)

/** Number of per-organism floating-point attributes: health=0, energy=1, age=2. */
#define N_ATTRS                 3

/** Safety ceiling for max_per_cell parameter. Rejects garbage inputs.
 *  REF: GOV-003 §5.4 (boundary condition handling) */
#define MAX_PER_CELL_LIMIT      16

/** Offspring initial health on spawn.
 *  PARITY: Must match phases.py:_spawn_offspring() "oa[..., 0] = 0.8" */
#define OFFSPRING_INITIAL_HEALTH  0.8f

/** Offspring initial energy on spawn.
 *  PARITY: Must match phases.py:_spawn_offspring() "oa[..., 1] = 0.4" */
#define OFFSPRING_INITIAL_ENERGY  0.4f

/** Offspring initial age on spawn (always zero — newborn).
 *  PARITY: Must match phases.py:_spawn_offspring() "oa[..., 2] = 0.0" */
#define OFFSPRING_INITIAL_AGE     0.0f

/** Fraction of parent energy retained after reproduction.
 *  PARITY: Must match phases.py:_spawn_offspring() "oa[..., 1] *= 0.5" */
#define PARENT_ENERGY_COST_FACTOR 0.5f

/** Number of possible movement directions (up, down, left, right). */
#define N_DIRECTIONS            4

/** Direction offsets: row deltas for {up, down, left, right}. */
static const int DR[N_DIRECTIONS] = {-1, 1, 0, 0};

/** Direction offsets: column deltas for {up, down, left, right}. */
static const int DC[N_DIRECTIONS] = {0, 0, -1, 1};


/* ══════════════════════════════════════════════════════════════════════
 * Helper: find_empty_slot
 *
 * Scans a single cell's species-grid slice for the first SPECIES_EMPTY
 * slot.  Used by both movement (target cell) and reproduction (offspring
 * placement).
 *
 * PRECONDITION:  sg points to a valid species_grid buffer of length ≥
 *                sg_base + mpc.
 * POSTCONDITION: Returns index in [0, mpc) if found, or -1 if full.
 * SIDE EFFECTS:  None (read-only scan).
 *
 * @param sg       Species grid flat buffer.
 * @param sg_base  Start offset of the cell within sg.
 * @param mpc      Max organisms per cell (slot count).
 * @return         Slot index [0, mpc) on success, -1 if cell is full.
 * ══════════════════════════════════════════════════════════════════════ */
static int
find_empty_slot(const uint8_t *sg, int sg_base, int mpc)
{
    for (int s = 0; s < mpc; s++) {
        if (sg[sg_base + s] == SPECIES_EMPTY) {
            return s;
        }
    }
    return -1;  /* Cell is full — no room for transfer or offspring */
}


/* ══════════════════════════════════════════════════════════════════════
 * Helper: transfer_organism
 *
 * Moves a single organism from source cell+slot to target cell+slot.
 * Copies species ID and all N_ATTRS floats, then zeroes the source.
 *
 * WHY a separate function: GOV-003 §4.1 mandates ≤60 lines per
 * function.  Extracting the transfer logic keeps phase_movement_c()
 * within the limit while making the data-move operation independently
 * testable and readable.
 *
 * PRECONDITION:  src and tgt offsets are valid within sg/oa buffers.
 *                tgt slot must be SPECIES_EMPTY (caller verified).
 * POSTCONDITION: Organism now exists at tgt; src slot is SPECIES_EMPTY
 *                with zeroed attributes.
 * SIDE EFFECTS:  Mutates sg and oa in-place.
 *
 * @param sg             Species grid flat buffer.
 * @param oa             Organism attributes flat buffer.
 * @param src_sg_offset  Source slot offset into sg.
 * @param tgt_sg_offset  Target slot offset into sg.
 * @param src_oa_offset  Source slot offset into oa (= slot * N_ATTRS).
 * @param tgt_oa_offset  Target slot offset into oa (= slot * N_ATTRS).
 * ══════════════════════════════════════════════════════════════════════ */
static void
transfer_organism(uint8_t *sg, float *oa,
                  int src_sg_offset, int tgt_sg_offset,
                  int src_oa_offset, int tgt_oa_offset)
{
    /* Copy species ID */
    sg[tgt_sg_offset] = sg[src_sg_offset];
    sg[src_sg_offset] = SPECIES_EMPTY;

    /* Copy all organism attributes (health, energy, age) */
    for (int a = 0; a < N_ATTRS; a++) {
        oa[tgt_oa_offset + a] = oa[src_oa_offset + a];
        oa[src_oa_offset + a] = 0.0f;
    }
}


/* ══════════════════════════════════════════════════════════════════════
 * Function: phase_movement_c
 *
 * Complete replacement for the Python phase_movement() function.
 * Handles the entire movement logic in C:
 *   1. Iterate all cells, find organisms of the given species
 *   2. Apply movement probability filter
 *   3. Pick random direction
 *   4. Validate grid bounds
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
 *                grid_h, grid_w > 0; mpc in [1, MAX_PER_CELL_LIMIT].
 * POSTCONDITION: Organism count is conserved (moved, not created/destroyed).
 * SIDE EFFECTS:  Mutates species_grid and organism_attrs in-place.
 *                Allocates and frees a temporary `moved` buffer.
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

    /* ── Assertions: boundary/sanity checks (GOV-003 §5.4, §11) ── */
    assert(grid_h > 0 && "grid_h must be positive");
    assert(grid_w > 0 && "grid_w must be positive");
    assert(mpc > 0 && mpc <= MAX_PER_CELL_LIMIT && "mpc out of safe range");
    assert(species_id > SPECIES_EMPTY && "species_id must be a real species");

    uint8_t *sg   = (uint8_t *)PyArray_DATA(sg_arr);
    float   *oa   = (float *)PyArray_DATA(oa_arr);
    float   *rnd  = (float *)PyArray_DATA(rand_arr);
    int32_t *dirs = (int32_t *)PyArray_DATA(dir_arr);

    const int cell_stride_sg = mpc;             /* species_grid stride per cell */
    const int cell_stride_oa = mpc * N_ATTRS;   /* organism_attrs stride per cell */
    int total_moves = 0;

    /* WHY calloc: Prevents double-movement within a single tick.
     * An organism that moves into a new cell must not be iterated again. */
    uint8_t *moved = (uint8_t *)calloc((size_t)grid_h * grid_w * mpc, sizeof(uint8_t));
    if (!moved) {
        return PyErr_NoMemory();
    }

    /* ── Single pass over all cells ─────────────────────────────── */
    for (int r = 0; r < grid_h; r++) {
        for (int c = 0; c < grid_w; c++) {
            const int cell_idx = r * grid_w + c;
            const int sg_base = cell_idx * cell_stride_sg;
            const int oa_base = cell_idx * cell_stride_oa;

            for (int s = 0; s < mpc; s++) {
                if (sg[sg_base + s] != (uint8_t)species_id) {
                    continue;  /* Not the target species — skip */
                }
                if (moved[sg_base + s]) {
                    continue;  /* Already moved this tick — prevent double-movement */
                }
                if (rnd[sg_base + s] >= move_prob) {
                    continue;  /* Failed movement probability roll — stays put */
                }

                /* WHY `& 3`: bitmask mod-4 is branchless and safe because
                 * dir_array values are pre-generated in {0,1,2,3}. The mask
                 * guards against any out-of-range values defensively. */
                const int d  = dirs[sg_base + s] & (N_DIRECTIONS - 1);
                const int tr = r + DR[d];
                const int tc = c + DC[d];

                /* Bounds check — reject moves outside the grid */
                if (tr < 0 || tr >= grid_h || tc < 0 || tc >= grid_w) {
                    break;  /* WHY break not continue: matches Python fallback
                             * behavior — one failed move aborts the entire
                             * source cell, preventing positional bias. */
                }

                /* Find empty slot in target cell */
                const int tgt_cell    = tr * grid_w + tc;
                const int tgt_sg_base = tgt_cell * cell_stride_sg;
                const int tgt_oa_base = tgt_cell * cell_stride_oa;
                const int ts = find_empty_slot(sg, tgt_sg_base, mpc);

                if (ts < 0) {
                    break;  /* WHY break: target cell full — same abort-cell
                             * semantics as the Python fallback. */
                }

                /* Transfer organism from source to target */
                transfer_organism(
                    sg, oa,
                    sg_base + s,                     /* src species offset */
                    tgt_sg_base + ts,                /* tgt species offset */
                    oa_base + s * N_ATTRS,           /* src attrs offset   */
                    tgt_oa_base + ts * N_ATTRS       /* tgt attrs offset   */
                );

                /* Mark destination slot as moved to prevent re-processing */
                moved[tgt_sg_base + ts] = 1;
                total_moves++;

                break;  /* WHY break: this source slot is now empty —
                         * no further organisms to process at this index. */
            }
        }
    }

    free(moved);

    /* Assertion: moves can never exceed total cells × slots (sanity check) */
    assert(total_moves >= 0 && "move count must be non-negative");
    assert(total_moves <= grid_h * grid_w * mpc && "moves exceeded theoretical max");

    return PyLong_FromLong(total_moves);
}


/* ══════════════════════════════════════════════════════════════════════
 * Function: phase_spawn_offspring_c
 *
 * Complete replacement for the Python _spawn_offspring() inner loop.
 * Handles the full spawning logic in C:
 *   1. Iterate all cells
 *   2. Find slots flagged for reproduction
 *   3. Find empty slots for offspring via find_empty_slot()
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
 *                grid_h, grid_w > 0; mpc in [1, MAX_PER_CELL_LIMIT].
 * POSTCONDITION: Offspring placed with health=OFFSPRING_INITIAL_HEALTH,
 *                energy=OFFSPRING_INITIAL_ENERGY, age=OFFSPRING_INITIAL_AGE.
 *                Parent energy multiplied by PARENT_ENERGY_COST_FACTOR.
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

    /* ── Assertions: boundary/sanity checks (GOV-003 §5.4, §11) ── */
    assert(grid_h > 0 && "grid_h must be positive");
    assert(grid_w > 0 && "grid_w must be positive");
    assert(mpc > 0 && mpc <= MAX_PER_CELL_LIMIT && "mpc out of safe range");
    assert(species_id > SPECIES_EMPTY && "species_id must be a real species");

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

            /* Find first reproducing slot in this cell */
            int rs = -1;
            for (int s = 0; s < mpc; s++) {
                if (repro[sg_base + s]) {
                    rs = s;
                    break;  /* WHY break: one offspring per cell per tick
                             * matches Python fallback semantics. */
                }
            }
            if (rs < 0) {
                continue;  /* No reproducer in this cell */
            }

            /* Find first empty slot for the offspring */
            const int es = find_empty_slot(sg, sg_base, mpc);
            if (es < 0) {
                continue;  /* Cell is full — cannot place offspring */
            }

            /* ── Place offspring with species-standard initial stats ── */
            sg[sg_base + es] = (uint8_t)species_id;
            oa[oa_base + es * N_ATTRS + 0] = OFFSPRING_INITIAL_HEALTH;
            oa[oa_base + es * N_ATTRS + 1] = OFFSPRING_INITIAL_ENERGY;
            oa[oa_base + es * N_ATTRS + 2] = OFFSPRING_INITIAL_AGE;

            /* Parent pays an energy cost for reproduction */
            oa[oa_base + rs * N_ATTRS + 1] *= PARENT_ENERGY_COST_FACTOR;

            total_spawned++;
        }
    }

    /* Assertion: spawns can never exceed total cells (one per cell max) */
    assert(total_spawned >= 0 && "spawn count must be non-negative");
    assert(total_spawned <= grid_h * grid_w && "spawns exceeded theoretical max");

    return PyLong_FromLong(total_spawned);
}


/* ══════════════════════════════════════════════════════════════════════
 * Module Definition
 *
 * REF: GOV-003 §4.2 (universal file layout — entry point last)
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
    {NULL, NULL, 0, NULL}   /* Sentinel — required by CPython module API */
};

static struct PyModuleDef phases_c_module = {
    PyModuleDef_HEAD_INIT,
    "_phases_c",
    "C-accelerated simulation phases for biosphere.core.\n\n"
    "Provides phase_movement_c() and phase_spawn_offspring_c()\n"
    "that replace entire Python phase functions, eliminating both\n"
    "Python for-loops and NumPy intermediate array overhead.\n\n"
    "COMPLIANCE: GOV-003 v2.2.0\n"
    "Refs: BLU-001 §4.3, GOV-003 §7.2",
    -1,
    PhasesC_methods,
    NULL, NULL, NULL, NULL  /* m_slots, m_traverse, m_clear, m_free */
};

/**
 * Module initialization entry point.
 *
 * Called by Python's import machinery when `import _phases_c` executes.
 * Initializes the NumPy C API (required for PyArray_DATA, etc.) and
 * registers the module's method table.
 *
 * FAILURE MODE: If import_array() fails (NumPy version mismatch),
 *               the module import raises ImportError and native.py
 *               falls back to pure-Python implementation.
 */
PyMODINIT_FUNC
PyInit__phases_c(void)
{
    import_array();  /* Initialize NumPy C API — must precede any array ops */
    return PyModule_Create(&phases_c_module);
}
