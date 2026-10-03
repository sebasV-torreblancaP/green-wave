from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from green_wave.models.errors import ConfigurationError

from .search_context import SearchContext


ScoreFunction = Callable[[int], float]


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    best_green_s: int
    best_score: float
    evaluated: int
    method: str
    generations: int = 0
    reason: str = "domain_evaluated"


class Optimizer(Protocol):
    def search(self, context: SearchContext, score: ScoreFunction) -> OptimizationResult:
        ...


def checked_score(value: object) -> float:
    if type(value) not in (float, int) or not isfinite(value) or not 0 <= value <= 1:
        raise ConfigurationError("la función objetivo debe devolver un número finito entre 0 y 1")
    return float(value)
