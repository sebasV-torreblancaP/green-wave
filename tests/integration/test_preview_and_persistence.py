import contextlib
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from green_wave.cli import main
from green_wave.models.intersection import IntersectionConfig
from green_wave.persistence.result_reader import read_trace
from green_wave.persistence.result_writer import write_trace
from green_wave.simulation.signal_simulator import simulate_fixed_signal


EXAMPLE = Path(__file__).resolve().parents[2] / "config/examples/synthetic/scenario.json"


class PreviewAndPersistenceTests(unittest.TestCase):
    def test_preview_uses_explicit_origin_and_selected_plan(self) -> None:
        output = StringIO()
        with contextlib.redirect_stdout(output):
            code = main([str(EXAMPLE), "--preview", "I1", "--plan", "A",
                         "--green-origin-s", "10", "--duration-s", "5"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "I1 [14, 19): VVVVV\n")

    def test_trace_round_trip(self) -> None:
        signal = IntersectionConfig("I", 6, 1, "standard")
        original = simulate_fixed_signal(signal, 2, green_origin_s=10, start_s=11, duration_s=7)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.json"
            write_trace(original, path)
            self.assertEqual(read_trace(path), original)


if __name__ == "__main__":
    unittest.main()
