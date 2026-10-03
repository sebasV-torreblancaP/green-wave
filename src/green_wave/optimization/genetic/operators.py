import random

from green_wave.models.errors import ConfigurationError


def reproduce(left: int, right: int, *, strategy: str, rng: random.Random) -> int:
    if strategy == "mean":
        total = left + right
        return total // 2 + (total % 2 and rng.randrange(2))
    if strategy == "copy":
        return rng.choice((left, right))
    raise ConfigurationError(f"operador de reproducción desconocido: {strategy}")


def mutate(green: int, *, probability: float, amplitude_s: int, rng: random.Random) -> int:
    if rng.random() >= probability:
        return green
    return green + rng.randint(-amplitude_s, amplitude_s)

