from dataclasses import dataclass

from green_wave.models.errors import InvalidCandidate
from green_wave.models.intersection import IntersectionConfig, require_integer

from .durations import red_duration


@dataclass(frozen=True, slots=True)
class IntegerDomain:
    lower: int
    upper: int

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise InvalidCandidate("el dominio de verdes está vacío")

    def __len__(self) -> int:
        return self.upper - self.lower + 1

    def __contains__(self, value: object) -> bool:
        return type(value) is int and self.lower <= value <= self.upper

    def values(self) -> range:
        return range(self.lower, self.upper + 1)


def physical_domain(intersection: IntersectionConfig) -> IntegerDomain:
    available = intersection.cycle_s - intersection.yellow_s
    return IntegerDomain(max(0, available - 99), min(99, available))


def next_green_domain(intersection: IntersectionConfig, current_green_s: int,
                      max_change_percent: int = 20) -> IntegerDomain:
    red_duration(intersection, current_green_s)
    require_integer(max_change_percent, "max_change_percent")
    if not 0 <= max_change_percent <= 100:
        raise InvalidCandidate("max_change_percent fuera de 0..100")
    physical = physical_domain(intersection)
    low_numerator = current_green_s * (100 - max_change_percent)
    high_numerator = current_green_s * (100 + max_change_percent)
    lower = max(physical.lower, (low_numerator + 99) // 100)
    upper = min(physical.upper, high_numerator // 100)
    return IntegerDomain(lower, upper)


def validate_next_green(intersection: IntersectionConfig, current_green_s: int,
                        proposed_green_s: int, max_change_percent: int = 20) -> None:
    require_integer(proposed_green_s, "proposed_green_s")
    domain = next_green_domain(intersection, current_green_s, max_change_percent)
    if proposed_green_s not in domain:
        raise InvalidCandidate(
            f"{intersection.id}: G={proposed_green_s} fuera de {domain.lower}..{domain.upper}"
        )

