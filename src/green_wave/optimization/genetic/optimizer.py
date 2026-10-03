from dataclasses import dataclass
from math import isfinite
import random

from green_wave.models.errors import ConfigurationError
from green_wave.optimization.interfaces import OptimizationResult, ScoreFunction, checked_score
from green_wave.optimization.search_context import SearchContext

from .operators import mutate, reproduce
from .population import fill_population, initial_population


@dataclass(frozen=True, slots=True)
class GeneticChoices:
    """Choices absent from Plan.md; callers must supply all values explicitly."""

    parent_strategy: str
    mutation_probability: float
    mutation_amplitude_s: int
    current_in_every_generation: bool
    seed: int

    def __post_init__(self) -> None:
        if self.parent_strategy not in ("mean", "copy"):
            raise ConfigurationError("parent_strategy debe ser mean o copy")
        rate = self.mutation_probability
        if type(rate) not in (int, float) or not isfinite(rate) or not 0 <= rate <= 1:
            raise ConfigurationError("mutation_probability debe estar en 0..1")
        if type(self.mutation_amplitude_s) is not int or self.mutation_amplitude_s < 0:
            raise ConfigurationError("mutation_amplitude_s debe ser un entero no negativo")
        if type(self.current_in_every_generation) is not bool:
            raise ConfigurationError("current_in_every_generation debe ser booleano")
        if type(self.seed) is not int:
            raise ConfigurationError("seed debe ser entero")


class GeneticOptimizer:
    def __init__(self, choices: GeneticChoices, *, population_size: int = 15,
                 elite_count: int = 5, max_generations: int = 100,
                 stagnation_generations: int = 10) -> None:
        if (type(population_size) is not int or type(elite_count) is not int
                or type(max_generations) is not int or type(stagnation_generations) is not int
                or min(population_size, elite_count, max_generations, stagnation_generations) <= 0
                or elite_count > population_size):
            raise ConfigurationError("parámetros de población o parada inválidos")
        self.choices = choices
        self.population_size = population_size
        self.elite_count = elite_count
        self.max_generations = max_generations
        self.stagnation_generations = stagnation_generations
        self.rng = random.Random(choices.seed)

    def search(self, context: SearchContext, score: ScoreFunction) -> OptimizationResult:
        domain = context.feasible_greens
        current = context.current_green_s
        population = initial_population(domain, current, self.population_size, self.rng)
        best_green = current
        best_score = -1.0
        stagnant = 0
        evaluations = 0
        reason = "max_generations"
        generations = 0

        for generation in range(1, self.max_generations + 1):
            generations = generation
            ranked: list[tuple[int, float]] = []
            for green in population:
                ranked.append((green, checked_score(score(green))))
                evaluations += 1
            ranked.sort(key=lambda item: item[1], reverse=True)
            top_green, top_score = ranked[0]
            if top_score > best_score:
                best_green, best_score = top_green, top_score
                stagnant = 0
            else:
                stagnant += 1
            if best_score == 1.0:
                reason = "perfect_fitness"
                break
            if stagnant >= self.stagnation_generations:
                reason = "stagnation"
                break

            elites = [green for green, _ in ranked[:min(self.elite_count, len(ranked))]]

            def offspring() -> int:
                left = self.rng.choice(elites)
                right = self.rng.choice(elites)
                child = reproduce(left, right, strategy=self.choices.parent_strategy, rng=self.rng)
                return mutate(child, probability=self.choices.mutation_probability,
                              amplitude_s=self.choices.mutation_amplitude_s, rng=self.rng)

            population = fill_population(domain, elites, current, self.population_size,
                                         self.choices.current_in_every_generation,
                                         self.rng, offspring)

        return OptimizationResult(best_green, best_score, evaluations, "genetic",
                                  generations, reason)
