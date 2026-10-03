import unittest

from green_wave.mathematics.durations import red_duration
from green_wave.mathematics.feasible_domain import next_green_domain, physical_domain, validate_next_green
from green_wave.models.errors import ConfigurationError, InvalidCandidate
from green_wave.models.intersection import IntersectionConfig


def intersection(cycle: int, yellow: int = 3) -> IntersectionConfig:
    return IntersectionConfig("I", cycle, yellow, "standard")


class DomainTests(unittest.TestCase):
    def test_plan_example_and_integer_rounding(self) -> None:
        signal = intersection(140)
        self.assertEqual((physical_domain(signal).lower, physical_domain(signal).upper), (38, 99))
        self.assertEqual((next_green_domain(signal, 50).lower, next_green_domain(signal, 50).upper), (40, 60))
        self.assertEqual((next_green_domain(signal, 56).lower, next_green_domain(signal, 56).upper), (45, 67))
        self.assertEqual(red_duration(signal, 50), 87)

    def test_small_greens_cannot_change_under_twenty_percent(self) -> None:
        signal = intersection(50)
        for green in range(5):
            with self.subTest(green=green):
                self.assertEqual(list(next_green_domain(signal, green).values()), [green])

    def test_domain_matches_independent_constraint_predicate(self) -> None:
        for cycle, yellow in ((3, 0), (50, 3), (99, 0), (140, 3), (198, 0), (199, 1)):
            signal = intersection(cycle, yellow)
            for current in physical_domain(signal).values():
                domain = next_green_domain(signal, current)
                expected = [candidate for candidate in range(100)
                            if 0 <= cycle - yellow - candidate <= 99
                            and 5 * abs(candidate - current) <= current]
                with self.subTest(cycle=cycle, yellow=yellow, current=current):
                    self.assertEqual(list(domain.values()), expected)

    def test_invalid_inputs_are_not_silently_repaired(self) -> None:
        with self.assertRaises(ConfigurationError):
            intersection(200, 1)
        with self.assertRaises(ConfigurationError):
            intersection(50, True)
        with self.assertRaises(InvalidCandidate):
            validate_next_green(intersection(100), 40, 60)


if __name__ == "__main__":
    unittest.main()

