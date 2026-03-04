"""Core simulation errors.

Independent of biosphere.infrastructure — the core module
has zero imports from any other biosphere.* module.
"""


class SimulationError(Exception):
    """Raised when the simulation enters an unrecoverable state.

    Examples: two consecutive NaN states, initialization failure.
    """


class InterventionError(Exception):
    """Raised when an intervention fails validation.

    This exception is NEVER raised by SimulationEngine.step() directly.
    It is raised by Intervention.validate() and caught internally by
    the engine. Defined here for use by callers who validate
    interventions independently.
    """
