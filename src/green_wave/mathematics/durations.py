from green_wave.models.errors import InvalidCandidate
from green_wave.models.intersection import IntersectionConfig, require_integer


def red_duration(intersection: IntersectionConfig, green_s: int) -> int:
    require_integer(green_s, "green_s")
    red_s = intersection.cycle_s - intersection.yellow_s - green_s
    if not 0 <= green_s <= 99 or not 0 <= red_s <= 99:
        raise InvalidCandidate(f"{intersection.id}: G={green_s}, R={red_s} fuera de 0..99")
    return red_s

