import csv
import json
import tempfile
import unittest
from pathlib import Path

from green_wave import Intersection, WavePlan, transition_to_target_offsets
from history import audit_history, export_history
from timeline import build_timeline


class HistoryTests(unittest.TestCase):
    def config(self):
        return dict(cycle=dict(common_cycle_s=120, yellow_s=4, green_base_s=[50]),
                    intersections=[dict(id='A', distance_from_s1_m=0)],
                    transition=dict(min_green_s=1, min_red_s=1))

    def timeline(self, offset=0, target=0):
        intersections = [Intersection('A', 0)]
        plan = WavePlan('up', 36, [offset])
        transition = transition_to_target_offsets([offset], [offset], [50], 120)
        return build_timeline(intersections, 120, 4, [50], plan, transition, 3, 3)

    def test_constant_plan_has_constant_observed_cycles(self):
        frames, states = self.timeline()
        with tempfile.TemporaryDirectory() as root:
            run, report = export_history(root, self.config(), frames, states)
            self.assertTrue(report['all_observed_cycles_constant'])
            self.assertEqual(report['nonconstant_cycles'], 0)
            self.assertEqual(report['sequence_issues'], [])
            self.assertTrue(report['global_windows_match_plan'])
            self.assertEqual(audit_history(run), report)

    def test_detects_distorted_cycles_even_when_frame_sums_are_correct(self):
        # Fixture deliberadamente inválida del algoritmo anterior. El nuevo
        # controlador la rechaza, pero la auditoría debe seguir detectándola.
        from timeline import phase_segments
        frames, states = [], []
        for c in range(8):
            offset = 0 if c < 3 else 10 if c == 3 else 20
            green = 60 if c in (3, 4) else 50
            stage = 'subida' if c < 3 else 'transicion' if c < 5 else 'bajada'
            frames.append(dict(intersection_id='A', global_cycle=c+1, stage=stage,
                               start_s=c*120, end_s=(c+1)*120, offset_s=offset,
                               green_s=green, yellow_s=4, red_s=116-green))
            for color, a, b in sorted(phase_segments(offset,green,4,120,c*120,(c+1)*120), key=lambda x:x[1]):
                if states and states[-1]['state'] == color:
                    states[-1]['end_s'] = b
                    states[-1]['duration_s'] = b-states[-1]['start_s']
                else:
                    states.append(dict(intersection_id='A',state=color,start_s=a,end_s=b,duration_s=b-a,
                                       stages=stage,left_censored=0,right_censored=0))
        states[-1]['right_censored'] = 1
        with tempfile.TemporaryDirectory() as root:
            run, report = export_history(root, self.config(), frames, states)
            self.assertTrue(report['global_windows_match_plan'])
            self.assertFalse(report['all_observed_cycles_constant'])
            self.assertEqual(report['nonconstant_cycles'], 2)
            self.assertEqual(report['intersections'][0]['max_cycle_s'], 130)
            with (run / 'cycles.csv').open(newline='', encoding='utf-8') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(sum(row['constant'] == '0' for row in rows), 2)

    def test_wrapped_same_color_is_merged_and_initial_partial_cycle_excluded(self):
        frames, states = self.timeline(offset=100, target=100)
        self.assertEqual(states[0]['state'], 'green')
        self.assertTrue(states[0]['left_censored'])
        self.assertEqual(states[0]['duration_s'], 30)
        self.assertTrue(any(row['start_s'] == 100 and row['end_s'] == 150 for row in states))
        with tempfile.TemporaryDirectory() as root:
            _, report = export_history(root, self.config(), frames, states)
            self.assertEqual(report['nonconstant_cycles'], 0)
            self.assertEqual(report['measured_complete_cycles'], 5)

    def test_audit_reads_disk_and_detects_invalid_color_sequence(self):
        frames, states = self.timeline()
        with tempfile.TemporaryDirectory() as root:
            run, report = export_history(root, self.config(), frames, states)
            path = run / 'states.csv'
            contents = path.read_text()
            path.write_text(contents.replace(',yellow,', ',red,', 1))
            report = audit_history(run)
            self.assertTrue(report['sequence_issues'])
            self.assertFalse(report['global_windows_match_plan'])

    def test_keeps_independent_run_snapshots(self):
        frames, states = self.timeline()
        cfg = self.config()
        with tempfile.TemporaryDirectory() as root:
            run1, _ = export_history(root, cfg, frames, states)
            cfg['note'] = 'segunda ejecución'
            run2, _ = export_history(root, cfg, frames, states)
            self.assertNotEqual(run1, run2)
            self.assertNotIn('note', json.loads((run1 / 'config.json').read_text()))
            self.assertEqual(json.loads((Path(root) / 'latest.json').read_text())['run_directory'], run2.name)


if __name__ == '__main__':
    unittest.main()
