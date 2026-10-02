import copy
import json
from pathlib import Path
import tempfile
import unittest

from history import export_history
from main import load_config
from green_wave import Intersection,WavePlan,calculate_wave_plan,find_down_green_target,transition_to_target_offsets
from timeline import build_timeline
from verify_fixed_cycle import verify_fixed_cycle_history


class PhysicalVerificationTests(unittest.TestCase):
    def export(self, root):
        cfg = copy.deepcopy(load_config())
        cfg['corridor'].update(speed_up_kmh=70,speed_down_kmh=35)
        cfg['simulation']['min_duration_s'] = 7200
        # Fixture del formato de archivo anterior. No es el algoritmo diario
        # ni sustituye el objetivo exacto; conserva la capacidad de auditar archivos antiguos.
        xs = [Intersection(x['id'],x['distance_from_s1_m']) for x in cfg['intersections']]
        up = calculate_wave_plan(xs,140,70,'up')
        ideal_down = calculate_wave_plan(xs,140,35,'down')
        base = cfg['cycle']['green_base_s']
        coordination = find_down_green_target(xs,up.offsets_s,base,140,3,35)
        tr = transition_to_target_offsets(up.offsets_s,up.offsets_s,base,140,
                                           max_change_fraction=.581396,max_cycles=200,yellow_s=3,
                                           target_green_s=coordination['target_green_s'])
        cfg['simulation']['cycles_down'] = 24
        frames, states, cycles = build_timeline(xs,140,3,base,up,tr,3,24,return_cycles=True)
        metadata = dict(up_offsets_s=up.offsets_s,
                        ideal_down_offsets_s=ideal_down.offsets_s,
                        final_offsets_s=tr.final_offsets_s,final_green_s=tr.final_green_s,
                        transition_cycles=tr.cycles_used,coordination=coordination)
        return export_history(root,cfg,frames,states,controller_cycles=cycles,plan_metadata=metadata)

    def test_long_history_proves_cycles_phases_and_down_arrivals(self):
        with tempfile.TemporaryDirectory() as root:
            run, report = self.export(root)
            self.assertEqual(report['nonconstant_cycles'],0)
            self.assertTrue(report['global_windows_match_plan'])
            for key in ('structural_issues','frame_issues','phase_issues','sequence_issues'):
                self.assertEqual(report[key],[])
            proof = verify_fixed_cycle_history(run)
            self.assertGreaterEqual(proof['total_time_s'],7200)
            self.assertTrue(proof['all_cycles_140_s'])
            self.assertTrue(proof['green_limits_valid'])
            self.assertTrue(proof['down_band_valid'])
            self.assertGreater(proof['complete_down_vehicles'],0)
            self.assertFalse(proof['ideal_down_offsets_reached'])
            self.assertTrue((run/'bajada_arrivals.csv').exists())

    def test_verifier_detects_tampered_physical_csv(self):
        with tempfile.TemporaryDirectory() as root:
            run, _ = self.export(root)
            path = run/'controller_cycles.csv'
            contents = path.read_text(encoding='utf-8')
            # Primer ciclo S1: -140,0,140,60,3,77. Cambiar el rojo no debe pasar.
            path.write_text(contents.replace(',60,3,77,',',60,3,76,',1),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'ciclo físico'):
                verify_fixed_cycle_history(run)

    def test_verifier_detects_false_down_band_claim(self):
        with tempfile.TemporaryDirectory() as root:
            run, _ = self.export(root)
            path = run/'run.json'
            metadata = json.loads(path.read_text(encoding='utf-8'))
            metadata['plan']['coordination']['departure_s'] = 120
            metadata['plan']['coordination']['departure_exact_s'] = '120'
            path.write_text(json.dumps(metadata),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'banda declarada'):
                verify_fixed_cycle_history(run)


if __name__ == '__main__':
    unittest.main()
