from collections.abc import Callable

from green_wave.models.candidate import FitnessBreakdown
from green_wave.models.errors import ConfigurationError
from green_wave.models.timeline import TemporalWindow

from .boundary_fitness import boundary_fitness
from .state_fitness import state_fitness


def evaluate(candidate: TemporalWindow, target: TemporalWindow,
             boundary_scorer: Callable[[TemporalWindow, TemporalWindow], float] = boundary_fitness
             ) -> FitnessBreakdown:
    state = state_fitness(candidate, target)
    boundary = boundary_scorer(candidate, target)
    if type(boundary) not in (int, float) or not 0 <= boundary <= 1:
        raise ConfigurationError("F_frontera debe estar en 0..1")
    return FitnessBreakdown(state.value, float(boundary),
                            0.5 * state.value + 0.5 * boundary,
                            state.different_seconds)

