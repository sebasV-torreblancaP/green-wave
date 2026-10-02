import copy
import unittest
from fractions import Fraction

from green_wave import (Intersection, calculate_wave_plan, transition_to_target_offsets,
                        find_down_green_target)
from main import load_config, validate_config
from simulation import prepare_simulation
from timeline import build_timeline
from visualization import green_departure_windows


class FixedCycleTransitionTests(unittest.TestCase):
    def test_compensation_and_real_cycles_across_global_boundaries(self):
        result = transition_to_target_offsets([0, 90], [0, 90], [50, 40], 120,
                                               yellow_s=4, target_green_s=[60, 32], green_step_s=2)
        self.assertEqual(result.cycles_used, 5)
        for gs, rs in zip(result.green_history, result.red_history):
            for i, base in enumerate([50, 40]):
                self.assertEqual(gs[i]+4+rs[i], 120)
                self.assertEqual(gs[i]-base, -(rs[i]-(120-base-4)))
                self.assertLessEqual(abs(gs[i]-base), base*.2)
        from green_wave import WavePlan
        xs = [Intersection('A', 0), Intersection('B', 100)]
        _, states, cycles = build_timeline(xs, 120, 4, [50, 40], WavePlan('up', 36, [0, 90]),
                                           result, 3, 3, return_cycles=True)
        self.assertTrue(all(c.duration_s == 120 for c in cycles))
        for identity in ('A', 'B'):
            own = [r for r in states if r['intersection_id'] == identity]
            starts = [r['start_s'] for r in own if r['state'] == 'green' and not r['left_censored']]
            self.assertTrue(all(b-a == 120 for a, b in zip(starts, starts[1:])))
            self.assertTrue(all(r['duration_s'] == 4 for r in own if r['state'] == 'yellow'))

    def test_no_extra_cycle_when_target_is_reached(self):
        result = transition_to_target_offsets([0], [0], [50], 120)
        self.assertEqual(result.cycles_used, 0)
        self.assertEqual(result.green_history, [])
        result = transition_to_target_offsets([0], [0], [50], 120, target_green_s=[55], green_step_s=2)
        self.assertEqual(result.green_history, [[52], [54], [55]])
        self.assertEqual(result.cycles_used, 3)

    def test_incompatible_offsets_are_rejected_even_with_many_cycles(self):
        # Antes se admitían y daban verdes separados por 130 s en vez de 120.
        for count in (20, 200, 1000):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'inalcanzables'):
                transition_to_target_offsets([0], [20], [50], 120, max_cycles=count)

    def test_optimized_reference_only_accepts_identical_relative_offsets(self):
        result = transition_to_target_offsets([0, 40], [10, 50], [50, 50], 120,
                                               optimize_target_phase=True)
        self.assertEqual(result.cycles_used, 0)
        self.assertEqual(result.final_offsets_s, [0, 40])
        self.assertEqual(result.target_phase_shift_s, -10)
        with self.assertRaisesRegex(ValueError, 'inalcanzables'):
            transition_to_target_offsets([0, 40], [10, 60], [50, 50], 120,
                                          optimize_target_phase=True)

    def test_red_minimum_limits_extension(self):
        with self.assertRaisesRegex(ValueError, 'mínimos'):
            transition_to_target_offsets([0], [0], [110], 120, yellow_s=4,
                                          min_red_s=2, target_green_s=[115])
        result = transition_to_target_offsets([0], [0], [110], 120, yellow_s=4,
                                               min_red_s=2, target_green_s=[114], green_step_s=2)
        self.assertEqual(result.red_history, [[4], [2]])

    def test_integer_capacity_and_consecutive_green_changes_are_limited(self):
        with self.assertRaisesRegex(ValueError, 'límite'):
            transition_to_target_offsets([0], [0], [53], 120, target_green_s=[64])
        result = transition_to_target_offsets([0], [0], [50], 120,
                                               target_green_s=[79], max_change_fraction=.58,
                                               green_step_s=100)
        self.assertEqual(result.green_history, [[79]])
        self.assertTrue(all(type(v) is int for row in result.green_history for v in row))

    def test_project_minimum_relaxation_is_global_for_one_second_band(self):
        cfg = load_config()
        xs = [Intersection(x['id'], x['distance_from_s1_m']) for x in cfg['intersections']]
        up = calculate_wave_plan(xs, 140, 70, 'up')
        result = find_down_green_target(xs, up.offsets_s, [60,40,55,53,43,65], 140, 3, 35)
        self.assertEqual(result['minimum_fraction'], '25/43')
        self.assertEqual(result['target_green_s'], [60,40,65,53,68,65])
        self.assertEqual(result['departure_s'], 113)
        self.assertGreaterEqual(max(b-a for a,b in result['windows_s']), 1)
        # El umbral inmediatamente anterior permite como máximo 67 s en S5.
        from green_wave import WavePlan
        below = Fraction(25,43) - Fraction(1,1_000_000)
        capacity = [g+int(g*below) for g in [60,40,55,53,43,65]]
        windows = green_departure_windows(xs, WavePlan('down',35,up.offsets_s), capacity,140)
        self.assertLess(sum(b-a for a,b in windows), 1)

    def test_original_twenty_percent_configuration_still_rejected(self):
        cfg = copy.deepcopy(load_config())
        cfg['corridor'].update(speed_up_kmh=70,speed_down_kmh=35)
        cfg['transition']['max_green_change_fraction_per_cycle'] = .2
        day = prepare_simulation(cfg)
        self.assertEqual(day.requests[0].status,'FAILED')
        self.assertIn('TARGET NOT ACHIEVABLE',day.requests[0].reason)
        self.assertEqual(day.cycles,day.baseline_cycles)

    def test_ramp_needs_twenty_five_cycles_and_extends_horizon(self):
        cfg = copy.deepcopy(load_config())
        cfg['corridor'].update(speed_up_kmh=70,speed_down_kmh=35)
        with self.assertRaisesRegex(ValueError, '25 ciclos'):
            transition_to_target_offsets([0],[0],[43],140,target_green_s=[68],
                                          max_change_fraction=.581396,max_cycles=20,yellow_s=3)
        ramp = transition_to_target_offsets([0],[0],[43],140,target_green_s=[68],
                                            max_change_fraction=.581396,max_cycles=200,yellow_s=3)
        self.assertEqual(ramp.cycles_used,25)
        self.assertEqual(ramp.green_history[0][0],44)
        self.assertEqual(ramp.green_history[-1][0],68)
        cfg['simulation']['min_duration_s'] = 7200
        cfg['day'].update(start='06:00',end='06:30',transition_time='06:15')
        result = prepare_simulation(cfg)
        self.assertGreaterEqual(result.total_s,7200)
        self.assertEqual(result.nominal_green_s,tuple(cfg['cycle']['green_base_s']))

    def test_band_crossing_zero_is_not_lost(self):
        # Un verde común [100,150) tiene banda continua de 50 s aunque la
        # referencia lo divida en [100,120) y [0,30).
        xs = [Intersection('A',0), Intersection('B',120)]
        result = find_down_green_target(xs, [100,100], [50,50],120,4,3.6,
                                        min_band_s=40)
        self.assertEqual(result['minimum_fraction'], '0')
        self.assertEqual(result['target_green_s'], [50,50])

    def test_timeline_rejects_any_offset_change_in_controller_commands(self):
        from green_wave import WavePlan
        result = transition_to_target_offsets([0],[0],[50],120,target_green_s=[51])
        result.offset_history[-1][0] = 1
        with self.assertRaisesRegex(ValueError,'no admite cambios'):
            build_timeline([Intersection('A',0)],120,4,[50],WavePlan('up',36,[0]),result,3,3)

    def test_generated_offsets_round_half_seconds_up(self):
        plan = calculate_wave_plan([Intersection('A',0), Intersection('B',315)],120,36,'up')
        self.assertEqual(plan.offsets_s, [0,32])

    def test_fractional_signal_inputs_are_rejected(self):
        for kwargs in ({'cycle_s':120.5}, {'yellow_s':3.5}, {'base_green_s':[50.1]},
                       {'current_offsets_s':[.5]}, {'target_offsets_s':[10.5]},
                       {'min_red_s':1.5}, {'target_green_s':[50.1]}, {'green_step_s':1.5}):
            arguments = dict(current_offsets_s=[0], target_offsets_s=[0],base_green_s=[50],cycle_s=120)
            arguments.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError,'segundos enteros'):
                transition_to_target_offsets(**arguments)

    def test_invalid_long_simulation_controls_are_rejected(self):
        for key, value in (('min_duration_s',-1), ('min_duration_s',.5), ('green_step_s',0), ('min_down_band_s',0)):
            cfg = copy.deepcopy(load_config())
            section = 'simulation' if key == 'min_duration_s' else 'transition'
            cfg[section][key] = value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                validate_config(cfg)


if __name__ == '__main__':
    unittest.main()
