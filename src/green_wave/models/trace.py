from dataclasses import dataclass

from .errors import ConfigurationError
from .phase import Phase


@dataclass(frozen=True, slots=True)
class PhaseSample:
    time_s: int
    phase: Phase


@dataclass(frozen=True, slots=True)
class PhaseChange:
    time_s: int
    previous: Phase
    next: Phase


@dataclass(frozen=True, slots=True)
class SignalTrace:
    intersection_id: str
    samples: tuple[PhaseSample, ...]
    changes: tuple[PhaseChange, ...]

    def __post_init__(self) -> None:
        if not self.samples:
            raise ConfigurationError("una traza debe contener al menos un segundo")

