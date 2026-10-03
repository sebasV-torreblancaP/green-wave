import unittest

from green_wave.models.intersection import IntersectionConfig
from green_wave.optimization.genetic.optimizer import GeneticChoices, GeneticOptimizer
from green_wave.optimization.search_context import SearchContext


def choices(seed: int = 7) -> GeneticChoices:
    return GeneticChoices("mean", 0.5, 5, True, seed)


class GeneticOptimizerTests(unittest.TestCase):
    def test_generations_preserve_unique_valid_population_and_incumbent(self) -> None:
        context = SearchContext(IntersectionConfig("I", 100, 3, "standard"), 40)
        seen: list[int] = []

        def score(green: int) -> float:
            seen.append(green)
            return 0.9 - abs(green - 48) / 100

        result = GeneticOptimizer(choices(), stagnation_generations=4).search(context, score)
        self.assertEqual(result.best_green_s, 48)
        self.assertEqual(result.reason, "stagnation")
        self.assertEqual(result.evaluated, 15 * result.generations)
        for start in range(0, len(seen), 15):
            generation = seen[start:start + 15]
            self.assertEqual(len(set(generation)), 15)
            self.assertIn(40, generation)
            self.assertTrue(all(32 <= green <= 48 for green in generation))

    def test_one_value_domain_stops_without_duplicate_candidates(self) -> None:
        context = SearchContext(IntersectionConfig("I", 50, 3, "standard"), 0)
        seen: list[int] = []

        def score(green: int) -> float:
            seen.append(green)
            return 0.5

        result = GeneticOptimizer(choices(), stagnation_generations=3).search(context, score)
        self.assertEqual(result.best_green_s, 0)
        self.assertEqual(result.reason, "stagnation")
        self.assertEqual(seen, [0, 0, 0, 0])

    def test_same_seed_reproduces_search(self) -> None:
        context = SearchContext(IntersectionConfig("I", 100, 3, "standard"), 40)
        score = lambda green: 0.8 - abs(green - 45) / 100
        self.assertEqual(GeneticOptimizer(choices()).search(context, score),
                         GeneticOptimizer(choices()).search(context, score))


if __name__ == "__main__":
    unittest.main()

