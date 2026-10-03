from dataclasses import dataclass

from green_wave.mathematics.feasible_domain import IntegerDomain, next_green_domain
from green_wave.models.intersection import IntersectionConfig


@dataclass(frozen=True, slots=True)
class SearchContext:
    intersection: IntersectionConfig
    current_green_s: int
    max_change_percent: int = 20

    @property
    def feasible_greens(self) -> IntegerDomain:
        return next_green_domain(self.intersection, self.current_green_s, self.max_change_percent)

