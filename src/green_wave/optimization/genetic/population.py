import random

from green_wave.mathematics.feasible_domain import IntegerDomain


def initial_population(domain: IntegerDomain, current: int, requested_size: int,
                       rng: random.Random) -> list[int]:
    remaining = [green for green in domain.values() if green != current]
    rng.shuffle(remaining)
    return [current, *remaining[:max(0, min(requested_size, len(domain)) - 1)]]


def fill_population(domain: IntegerDomain, elites: list[int], current: int,
                    requested_size: int, keep_current: bool, rng: random.Random,
                    offspring_factory) -> list[int]:
    effective_size = min(requested_size, len(domain))
    population = list(elites)
    if keep_current and current not in population and len(population) < effective_size:
        population.append(current)
    remaining = {value for value in domain.values() if value not in population}
    attempts = 0
    maximum_attempts = max(20, 10 * len(domain))
    while len(population) < effective_size and remaining and attempts < maximum_attempts:
        attempts += 1
        child = offspring_factory()
        if child in remaining:
            population.append(child)
            remaining.remove(child)
    if len(population) < effective_size:
        spare = list(remaining)
        rng.shuffle(spare)
        population.extend(spare[:effective_size - len(population)])
    return population

