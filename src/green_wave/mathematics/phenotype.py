from green_wave.models.intersection import IntersectionConfig

from .durations import red_duration


def nominal_period(intersection: IntersectionConfig, green_s: int) -> str:
    """Canonical duration encoding; no claim about its physical time origin."""
    red_s = red_duration(intersection, green_s)
    return "V" * green_s + "A" * intersection.yellow_s + "R" * red_s

