from dataclasses import dataclass
from math import isfinite

from .errors import ConfigurationError
from .intersection import require_integer


@dataclass(frozen=True, slots=True)
class Candidate:
    green_s: int

    def __post_init__(self) -> None:
        require_integer(self.green_s, "green_s")


@dataclass(frozen=True, slots=True)
class FitnessBreakdown:
    state: float
    boundary: float
    total: float
    different_seconds: tuple[int, ...]

    def __post_init__(self) -> None:
        for name in ("state", "boundary", "total"):
            value = getattr(self, name)
            if type(value) not in (float, int) or not isfinite(value) or not 0 <= value <= 1:
                raise ConfigurationError(f"{name}: fitness fuera de 0..1")

