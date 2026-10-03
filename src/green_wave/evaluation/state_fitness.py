from dataclasses import dataclass

from green_wave.models.errors import ConfigurationError
from green_wave.models.timeline import TemporalWindow


@dataclass(frozen=True, slots=True)
class StateScore:
    value: float
    different_seconds: tuple[int, ...]


def state_fitness(candidate: TemporalWindow, target: TemporalWindow) -> StateScore:
    if candidate.duration_s != target.duration_s or candidate.start_s != target.start_s:
        raise ConfigurationError("las ventanas deben tener igual duración y origen temporal")
    different = tuple(index for index, (left, right) in enumerate(zip(candidate.states, target.states))
                      if left != right)
    return StateScore(1 - len(different) / candidate.duration_s, different)

