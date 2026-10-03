import unittest

from green_wave.evaluation.evaluator import evaluate
from green_wave.evaluation.boundary_fitness import boundary_fitness
from green_wave.evaluation.state_fitness import state_fitness
from green_wave.mathematics.periodic_time import observable_boundaries, rotated_window
from green_wave.mathematics.phenotype import nominal_period
from green_wave.models.errors import ConfigurationError, ModelDecisionRequired
from green_wave.models.intersection import IntersectionConfig
from green_wave.models.phase import BoundaryKind
from green_wave.models.timeline import TemporalWindow


class TemporalAndFitnessTests(unittest.TestCase):
    def test_rotation_corrects_plan_example_and_preserves_counts(self) -> None:
        nominal = nominal_period(IntersectionConfig("I", 14, 2, "standard"), 5)
        self.assertEqual(nominal, "VVVVVAARRRRRRR")
        rotated = rotated_window(nominal, 2, 123)
        self.assertEqual(rotated.states, "VVVAARRRRRRRVV")
        self.assertEqual(rotated.start_s, 123)
        self.assertEqual({phase: rotated.states.count(phase) for phase in "RVA"},
                         {phase: nominal.count(phase) for phase in "RVA"})

    def test_wrap_boundary_is_detected_in_periodic_window(self) -> None:
        window = TemporalWindow(5, "RVVA")
        self.assertEqual([(event.kind, event.position_s) for event in observable_boundaries(window)], [
            (BoundaryKind.YELLOW_TO_RED, 0),
            (BoundaryKind.RED_TO_GREEN, 1),
            (BoundaryKind.GREEN_TO_YELLOW, 3),
        ])

    def test_state_fitness_and_compatible_windows(self) -> None:
        target = TemporalWindow(4, "RRVVAA")
        self.assertEqual(state_fitness(target, target).value, 1)
        candidate = TemporalWindow(4, "RRVRAA")
        score = state_fitness(candidate, target)
        self.assertEqual(score.different_seconds, (3,))
        self.assertAlmostEqual(score.value, 5 / 6)
        with self.assertRaises(ConfigurationError):
            state_fitness(candidate, TemporalWindow(5, "RRVVAA"))

    def test_full_fitness_requires_boundary_decision(self) -> None:
        window = TemporalWindow(0, "RVVA")
        with self.assertRaises(ModelDecisionRequired):
            evaluate(window, window)
        score = evaluate(window, window, lambda candidate, target: 1.0)
        self.assertEqual(score.total, 1.0)
        with self.assertRaises(ConfigurationError):
            evaluate(window, window, lambda candidate, target: 2.0)

    def test_explicit_boundary_metrics_differ_across_period_wrap(self) -> None:
        target = TemporalWindow(0, "VVAAARRR")
        shifted = TemporalWindow(0, "VAAARRRV")
        self.assertEqual(boundary_fitness(target, target, "circular"), 1)
        self.assertEqual(boundary_fitness(shifted, target, "circular"), 0.75)
        self.assertAlmostEqual(boundary_fitness(shifted, target, "linear"), 4 / 7)

    def test_zero_duration_phase_needs_border_policy(self) -> None:
        without_green = TemporalWindow(0, "AARR")
        with self.assertRaises(ModelDecisionRequired):
            boundary_fitness(without_green, without_green, "circular")


if __name__ == "__main__":
    unittest.main()
