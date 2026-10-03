import unittest

from green_wave.models.errors import ConfigurationError
from green_wave.models.intersection import IntersectionConfig
from green_wave.optimization.exhaustive import ExhaustiveOptimizer
from green_wave.optimization.search_context import SearchContext
from green_wave.simulation.signal_simulator import simulate_fixed_signal
from green_wave.visualization.signal_timeline import render_text_timeline


class ReferenceAndSimulationTests(unittest.TestCase):
    def test_reference_finds_best_valid_green_without_regression(self) -> None:
        signal = IntersectionConfig("I", 100, 3, "standard")
        context = SearchContext(signal, 40)
        result = ExhaustiveOptimizer().search(context, lambda green: 1 - abs(green - 50) / 100)
        self.assertEqual((result.best_green_s, result.best_score, result.evaluated), (48, 0.98, 17))
        self.assertEqual(result.method, "exhaustive")

    def test_equal_scores_preserve_current_in_reference(self) -> None:
        signal = IntersectionConfig("I", 100, 3, "standard")
        result = ExhaustiveOptimizer().search(SearchContext(signal, 40), lambda green: 0.7)
        self.assertEqual(result.best_green_s, 40)
        with self.assertRaises(ConfigurationError):
            ExhaustiveOptimizer().search(SearchContext(signal, 40), lambda green: float("nan"))

    def test_fixed_signal_trace_respects_supplied_origin(self) -> None:
        signal = IntersectionConfig("I", 6, 1, "standard")
        trace = simulate_fixed_signal(signal, 2, green_origin_s=10, start_s=11, duration_s=7)
        self.assertEqual(render_text_timeline(trace), "I [11, 18): VARRRVV")
        self.assertEqual([(change.time_s, change.previous.value, change.next.value)
                          for change in trace.changes],
                         [(12, "V", "A"), (13, "A", "R"), (16, "R", "V")])


if __name__ == "__main__":
    unittest.main()
