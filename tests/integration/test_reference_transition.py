from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
import csv
import xml.etree.ElementTree as ET

from green_wave.algorithms.transition_engine import run_reference
from green_wave.algorithms.transition_engine import run_genetic
from green_wave.algorithms.transition_policy import ReferencePolicy
from green_wave.configuration.loader import load_reference_policy, load_scenario
from green_wave.configuration.loader import load_genetic_choices
from green_wave.models.transition import TransitionStatus
from green_wave.persistence.result_reader import read_trace
from green_wave.persistence.result_writer import write_transition_result
from green_wave.simulation.signal_simulator import simulate_fixed_signal


EXAMPLE = Path(__file__).resolve().parents[2] / "config/examples/synthetic"


class ReferenceTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = load_scenario(EXAMPLE / "scenario.json")
        self.policy = load_reference_policy(EXAMPLE / "phase_origins.json", self.scenario, "circular")

    def test_all_six_reach_target_with_local_cycles_and_continuous_signals(self) -> None:
        result = run_reference(self.scenario, self.policy)
        self.assertEqual(result.status, TransitionStatus.COMPLETED)
        self.assertEqual(result.ended_at_s, 210)
        self.assertEqual(len(result.steps), 7)
        self.assertEqual([step.next_green_s for step in result.steps if step.intersection_id == "I1"], [48, 50])
        self.assertEqual(set(result.final_fitness.values()), {1.0})
        self.assertEqual([(event.previous.value, event.next.value) for event in result.traces["I1"].changes
                          if event.time_s == 110], [("R", "V")])
        for key, trace in result.traces.items():
            signal = self.scenario.intersections[key]
            target = simulate_fixed_signal(signal, self.scenario.plan_b.entries[key].green_s,
                                           green_origin_s=self.policy.plan_b_green_origins_s[key],
                                           start_s=result.ended_at_s,
                                           duration_s=signal.cycle_s)
            actual = tuple(sample.phase for sample in trace.samples
                           if result.ended_at_s <= sample.time_s < result.ended_at_s + signal.cycle_s)
            self.assertEqual(actual, tuple(sample.phase for sample in target.samples), key)

    def test_initially_equal_plans_need_no_changes(self) -> None:
        scenario = replace(self.scenario, plan_b=self.scenario.plan_a)
        result = run_reference(scenario, self.policy)
        self.assertEqual(result.status, TransitionStatus.COMPLETED)
        self.assertEqual(result.steps, ())
        self.assertEqual(result.ended_at_s, scenario.h_inicio_s)

    def test_local_cycle_limit_reports_incomplete(self) -> None:
        settings = replace(self.scenario.transition, max_transition_cycles=1)
        scenario = replace(self.scenario, transition=settings)
        result = run_reference(scenario, self.policy)
        self.assertEqual(result.status, TransitionStatus.INCOMPLETE_LIMIT)
        self.assertEqual(result.ended_at_s, 110)
        self.assertLess(result.final_fitness["I1"], 1)

    def test_unrepresentable_target_is_reported_before_search(self) -> None:
        origins_b = dict(self.policy.plan_b_green_origins_s)
        origins_b["I1"] += 1
        policy = replace(self.policy, plan_b_green_origins_s=origins_b)
        result = run_reference(self.scenario, policy)
        self.assertEqual(result.status, TransitionStatus.UNREACHABLE)
        self.assertEqual(result.steps, ())
        self.assertIn("I1", result.diagnostics)

    def test_small_green_cannot_reach_different_target(self) -> None:
        signal = replace(self.scenario.intersections["I1"], cycle_s=50)
        intersections = dict(self.scenario.intersections)
        intersections["I1"] = signal
        from green_wave.models.plan import PlanEntry, SignalPlan
        entries_a = dict(self.scenario.plan_a.entries)
        entries_b = dict(self.scenario.plan_b.entries)
        entries_a["I1"] = PlanEntry(4)
        entries_b["I1"] = PlanEntry(5)
        scenario = replace(self.scenario, intersections=intersections,
                           plan_a=SignalPlan("A", entries_a), plan_b=SignalPlan("B", entries_b))
        result = run_reference(scenario, self.policy)
        self.assertEqual(result.status, TransitionStatus.UNREACHABLE)
        self.assertIn("±20 %", result.diagnostics["I1"])

    def test_exported_result_contains_policy_and_readable_traces(self) -> None:
        result = run_reference(self.scenario, self.policy)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            write_transition_result(result, self.scenario, self.policy, output)
            summary = json.loads((output / "run.json").read_text(encoding="utf-8"))
            effective = json.loads((output / "effective_config.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(effective["plan_a_green_origins_s"], dict(self.policy.plan_a_green_origins_s))
            self.assertEqual(read_trace(output / "trace_I1.json"), result.traces["I1"])
            with (output / "transitions.csv").open(encoding="utf-8", newline="") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), len(result.steps))
            for name in ("signals.svg", "fitness.svg"):
                self.assertEqual(ET.parse(output / name).getroot().tag,
                                 "{http://www.w3.org/2000/svg}svg")

    def test_explicit_genetic_choices_complete_synthetic_transition(self) -> None:
        choices = load_genetic_choices(EXAMPLE / "genetic_choices.json")
        result = run_genetic(self.scenario, self.policy, choices)
        self.assertEqual(result.status, TransitionStatus.COMPLETED)
        self.assertEqual(result.method, "genetic")
        self.assertEqual(dict(result.final_green_s),
                         {key: entry.green_s for key, entry in self.scenario.plan_b.entries.items()})
        self.assertTrue(all(step.evaluated_candidates >= 1 for step in result.steps))
        self.assertEqual(result.optimizer_parameters["seed"], 12345)


if __name__ == "__main__":
    unittest.main()
