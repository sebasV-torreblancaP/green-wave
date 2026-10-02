import copy
import unittest

from green_wave import Intersection, WavePlan, calculate_wave_plan
from main import load_config, validate_config
from visualization import green_departure_windows, phase_segments


class WaveDiagramTests(unittest.TestCase):
    def test_wrapped_phases_cover_entire_cycle(self):
        segments = sorted(phase_segments(100, 50, 4, 120, 0, 120), key=lambda s: s[1])
        self.assertEqual(segments, [("green", 0, 30), ("yellow", 30, 34),
                                    ("red", 34, 100), ("green", 100, 120)])

    def test_wave_window_depends_on_offsets_and_green(self):
        intersections = [Intersection("A", 0), Intersection("B", 100)]
        plan = calculate_wave_plan(intersections, 60, 36, "up")
        self.assertEqual(green_departure_windows(intersections, plan, [20, 15], 60), [(0, 15)])
        manual = WavePlan("up", 36, [0, 40])
        self.assertEqual(green_departure_windows(intersections, manual, [20, 15], 60), [])

    def test_reverse_direction_window(self):
        intersections = [Intersection("A", 0), Intersection("B", 100)]
        plan = calculate_wave_plan(intersections, 60, 36, "down")
        self.assertEqual(green_departure_windows(intersections, plan, [20, 15], 60), [(0, 15)])

    def test_config_rejects_invalid_phase_duration(self):
        cfg = copy.deepcopy(load_config())
        cfg["cycle"]["green_base_s"][0] = cfg["cycle"]["common_cycle_s"] - cfg["cycle"]["yellow_s"] + 1
        with self.assertRaises(ValueError):
            validate_config(cfg)

    def test_both_original_stable_wave_plans_keep_base_cycles(self):
        from green_wave import transition_to_target_offsets
        from timeline import build_timeline
        intersections = [Intersection(str(i),d) for i,d in enumerate([0,350,870,1150,1760,2190])]
        greens = [60,40,55,53,43,65]
        for direction,speed in (('up',70),('down',35)):
            plan = calculate_wave_plan(intersections,140,speed,direction)
            tr = transition_to_target_offsets(plan.offsets_s,plan.offsets_s,greens,140,yellow_s=3)
            _,states = build_timeline(intersections,140,3,greens,plan,tr,3,3)
            self.assertGreater(sum(b-a for a,b in green_departure_windows(intersections,plan,greens,140)),0)
            for i,inter in enumerate(intersections):
                own = [r for r in states if r['intersection_id'] == inter.id]
                starts = [r['start_s'] for r in own if r['state'] == 'green' and not r['left_censored']]
                self.assertTrue(all(b-a == 140 for a,b in zip(starts,starts[1:])))
                self.assertTrue(all(r['duration_s'] == greens[i] for r in own
                                    if r['state'] == 'green' and not r['left_censored'] and not r['right_censored']))


if __name__ == "__main__":
    unittest.main()
