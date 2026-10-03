import json
from pathlib import Path
import shutil
import tempfile
import unittest

from green_wave.configuration.loader import load_scenario
from green_wave.models.errors import ConfigurationError


EXAMPLE = Path(__file__).resolve().parents[2] / "config/examples/synthetic"


class ConfigurationTests(unittest.TestCase):
    def test_synthetic_six_intersections_load_without_physical_data_claim(self) -> None:
        scenario = load_scenario(EXAMPLE / "scenario.json")
        self.assertEqual(len(scenario.intersections), 6)
        self.assertEqual(scenario.plan_a.entries["I1"].green_s, 40)
        self.assertEqual(scenario.plan_b.entries["I6"].green_s, 65)

    def test_incomplete_plan_has_named_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "synthetic"
            shutil.copytree(EXAMPLE, destination)
            path = destination / "plans/plan_b.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            del data["entries"]["I6"]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "exactamente"):
                load_scenario(destination / "scenario.json")

    def test_boolean_duration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "synthetic"
            shutil.copytree(EXAMPLE, destination)
            path = destination / "intersections/I1.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cycle_s"] = True
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "entero"):
                load_scenario(destination / "scenario.json")


if __name__ == "__main__":
    unittest.main()

