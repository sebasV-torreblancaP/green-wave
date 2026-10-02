import unittest

from continuous import LocalCycle, cycle_events, fixed_cycle_feasibility


class ContinuousEventsTests(unittest.TestCase):
    def test_only_horizon_ends_are_clipped(self):
        cycles = [LocalCycle('A', t, 50, 4, 66, 'subida') for t in (-20, 100, 220)]
        events = cycle_events(cycles, 300)
        self.assertEqual(events[0]['duration_s'], 30)
        self.assertTrue(events[0]['left_censored'])
        greens = [e for e in events if e['state'] == 'green' and not e['left_censored']]
        self.assertEqual([e['duration_s'] for e in greens], [50, 50])
        self.assertEqual(greens[1]['start_s'] - greens[0]['start_s'], 120)
        self.assertTrue(events[-1]['right_censored'])

    def test_green_extension_compensated_by_red_preserves_cycle_start(self):
        cycles = [LocalCycle('A', 0, 50, 4, 66, 'subida'),
                  LocalCycle('A', 120, 60, 4, 56, 'transicion'),
                  LocalCycle('A', 240, 50, 4, 66, 'bajada')]
        events = cycle_events(cycles, 360)
        self.assertEqual([e['start_s'] for e in events if e['state'] == 'green'], [0, 120, 240])
        self.assertEqual([e['duration_s'] for e in events if e['state'] == 'yellow'], [4, 4, 4])

    def test_rejects_jump_instead_of_cutting_a_phase(self):
        with self.assertRaisesRegex(ValueError, 'salto o solapamiento'):
            cycle_events([LocalCycle('A', 0, 50, 4, 66, 'subida'),
                          LocalCycle('A', 110, 50, 4, 66, 'transicion')], 230)

    def test_rejects_nonconstant_physical_period_even_without_gaps(self):
        with self.assertRaisesRegex(ValueError, 'duración de cada ciclo'):
            cycle_events([LocalCycle('A',0,50,4,76,'transicion')],130,expected_cycle_s=120)

    def test_zero_yellow_and_integer_validation(self):
        events = cycle_events([LocalCycle('A', 0, 50, 0, 70, 'subida')], 120)
        self.assertEqual([e['state'] for e in events], ['green', 'red'])
        with self.assertRaisesRegex(ValueError, 'enteros'):
            LocalCycle('A', 0, 50.5, 4, 66, 'subida')

    def test_fixed_cycle_feasibility_requires_one_common_reference(self):
        self.assertTrue(fixed_cycle_feasibility([0, 20], [10, 30], 120)['feasible'])
        self.assertFalse(fixed_cycle_feasibility([0, 20], [10, 30], 120, False)['feasible'])
        self.assertFalse(fixed_cycle_feasibility([0, 20], [10, 40], 120)['feasible'])


if __name__ == '__main__':
    unittest.main()
