from collections.abc import Mapping


def all_aligned(fitness_by_intersection: Mapping[str, float]) -> bool:
    return bool(fitness_by_intersection) and all(score == 1.0 for score in fitness_by_intersection.values())

