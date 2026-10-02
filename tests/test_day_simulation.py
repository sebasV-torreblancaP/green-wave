import copy
import csv
import json
import tempfile
from dataclasses import asdict

import pytest

from continuous import LocalCycle
from day_simulation import simulate_day
from green_wave import assess_phase_offset,choose_nominal_green
from history import query_history_state
from main import load_config,validate_config
from simulation import prepare_simulation
from verify_day import verify_day_history


OFFSETS_A = [0,18,45,59,91,113]
NOMINAL = [60,40,55,53,43,65]


def case_config():
    cfg = copy.deepcopy(load_config())
    cfg['cycle'].update(common_cycle_s=140,yellow_s=3,green_base_s=NOMINAL.copy())
    cfg['transition'].update(max_green_change_fraction_per_cycle=.2,max_transition_cycles=200,
                             min_green_s=1,max_green_s=136,min_red_s=1,green_step_s=1)
    cfg['waves'] = dict(A=dict(direction='up',speed_kmh=70,offsets_s=OFFSETS_A.copy()),
                        B=dict(direction='down',speed_kmh=cfg['corridor']['speed_down_kmh']))
    cfg['day'].update(date='2026-10-02',start='06:00',end='08:00',transition_time='06:16:15',
                       initial_wave='A',target_wave='B',post_transition_s=3600)
    cfg['simulation']['min_duration_s'] = 3600
    return cfg


def recovery_day(cfg=None):
    cfg = case_config() if cfg is None else cfg
    # Un objetivo compatible se declara explícitamente; no se sustituye el
    # objetivo original del caso obligatorio para simular un SUCCESS falso.
    cfg['waves']['B'] = dict(direction='up',speed_kmh=70,offsets_s=OFFSETS_A.copy())
    baseline = simulate_day(config=cfg,start='06:00',end='08:00')
    t = baseline.seconds('06:16:15')
    initial = baseline.state_at(t)
    deviations = [-2,3,-1,1,0,0]
    thresholds = {s['intersection_id']:s['cycle_start_s'] for s in initial}
    ids = {s['intersection_id']:i for i,s in enumerate(initial)}
    imported = []
    for c in baseline.cycles:
        i = ids[c.intersection_id]
        g = c.green_s+deviations[i] if c.start_s >= thresholds[c.intersection_id] else c.green_s
        imported.append(LocalCycle(c.intersection_id,c.start_s,g,3,137-g,c.stage))
    return simulate_day(config=cfg,start='06:00',end='08:00',controller_cycles=imported)


def test_full_day_required_case_reports_unreachable_and_keeps_nominal():
    cfg = case_config()
    cfg['day'].update(end='22:00',transition_time='13:37:24')
    original = copy.deepcopy(cfg)
    day = prepare_simulation(cfg)
    request = day.requests[0]
    assert cfg == original
    assert request.status == 'FAILED'
    assert request.reason.startswith('TARGET NOT ACHIEVABLE UNDER CURRENT CONSTRAINTS')
    assert not request.transition_complete and not request.target_achievable
    assert request.transition_cycles == 0 and request.decisions == []
    assert day.cycles == day.baseline_cycles
    assert day.states == day.baseline_states
    assert day.waves['A'].offsets_s == OFFSETS_A
    assert day.waves['B'].offsets_s != OFFSETS_A
    assert day.nominal_green_s == tuple(NOMINAL)
    assert day.nominal_red_s == (77,97,82,84,94,72)
    states = day.state_at('13:37:24')
    assert states[0]['phase'] == 'green' and states[0]['phase_elapsed_s'] == 4
    assert states[1]['phase'] == 'red' and states[1]['phase_elapsed_s'] == 83
    assert states[5]['phase'] == 'green' and states[5]['phase_elapsed_s'] == 31
    with tempfile.TemporaryDirectory() as root:
        run,audit = day.export(root)
        assert audit['nonconstant_cycles'] == 0
        assert audit['sequence_issues'] == audit['phase_issues'] == []
        proof = verify_day_history(run)
        assert proof['total_time_s'] >= 16*3600
        assert proof['target_offsets_reached'] is False
        assert proof['final_green_s'] == NOMINAL
        assert proof['final_reds_nominal']
        queried = query_history_state(run,'13:37:24')
        for live,saved in zip(states,queried):
            assert all(live[k] == value for k,value in saved.items())
        summary = json.loads((run/'transition_summary.json').read_text(encoding='utf-8'))[0]
        assert summary['initial_state'] == summary['final_state']
        assert summary['assessment'] == 'TARGET NOT ACHIEVABLE UNDER CURRENT CONSTRAINTS'


def test_request_preserves_mixed_green_amber_red_and_elapsed_times():
    day = simulate_day(config=case_config(),start='06:00',end='08:00')
    initial = day.state_at('06:16:15')
    assert {s['phase'] for s in initial} == {'green','yellow','red'}
    assert initial[4]['phase'] == 'yellow' and initial[4]['phase_elapsed_s'] == 1
    before = list(day.cycles)
    result = day.transition('06:16:15')
    assert result.initial_state == initial
    assert result.final_state == initial
    assert day.cycles == before
    assert not any(s['phase_elapsed_s'] == 0 for s in initial)


@pytest.mark.parametrize('intersection',range(6))
@pytest.mark.parametrize('phase',('green','yellow','red'))
def test_request_in_each_phase_of_each_intersection(intersection,phase):
    day = simulate_day(config=case_config(),start='06:00',end='08:00')
    origin = OFFSETS_A[intersection]+6*140
    t = origin+({'green':0,'yellow':NOMINAL[intersection],'red':NOMINAL[intersection]+3}[phase])
    current = day.state_at(t)
    assert current[intersection]['phase'] == phase
    assert current[intersection]['phase_elapsed_s'] == 0
    result = day.transition(t)
    assert result.initial_state == current == result.final_state
    assert day.cycles == day.baseline_cycles


def test_physical_initial_cycle_is_not_reset_at_day_start():
    day = simulate_day(config=case_config(),start='06:00',end='08:00')
    initial = day.state_at('06:00')
    assert initial[5]['phase'] == 'green' and initial[5]['phase_elapsed_s'] == 27
    assert initial[5]['cycle_start_s'] == -27
    request = day.transition('06:00')
    assert request.final_state == initial
    assert request.final_state[5]['phase_elapsed_s'] == 27


def test_dynamic_recovery_increases_and_decreases_without_moving_offsets():
    day = recovery_day()
    nominal_copy = day.nominal_green_s
    before = list(day.cycles)
    initial = day.state_at('06:16:15')
    request = day.transition('06:16:15')
    assert request.status == 'SUCCESS' and request.transition_complete
    assert request.transition_cycles == 3
    assert request.transition_duration_s == 303
    assert {d['phase_duration_adjustment']['green_delta_s'] for d in request.decisions} == {-1,1}
    assert day.nominal_green_s == nominal_copy
    for d in request.decisions:
        assert abs(d['green_error_s']) < abs(d['green_error_before_s'])
        assert d['phase_duration_adjustment']['red_delta_s'] == -d['phase_duration_adjustment']['green_delta_s']
        assert d['phase_offset_correction']['requested_s'] == d['phase_offset_correction']['applied_s'] == 0
        assert d['time_s'] % 140 == d['offset_s']
    preserved = [c for c in day.cycles if c.start_s < day.seconds('06:16:15')]
    assert preserved == [c for c in before if c.start_s < day.seconds('06:16:15')]
    assert request.initial_state == initial
    assert [s['green_s'] for s in request.final_state] == NOMINAL
    assert [s['red_s'] for s in request.final_state] == [77,97,82,84,94,72]
    assert day.total_s-request.transition_end_s >= 3600
    with tempfile.TemporaryDirectory() as root:
        run,audit = day.export(root)
        assert audit['nonconstant_cycles'] == 0
        proof = verify_day_history(run)
        assert proof['target_offsets_reached'] and proof['nominal_restored_after_success']
        assert proof['final_green_s'] == NOMINAL
        assert proof['stable_after_success_s'][0] >= 3600
        rows = list(csv.DictReader((run/'transitions.csv').open(encoding='utf-8',newline='')))
        assert sum(r['status'] == 'APPLIED' for r in rows) == len(request.decisions)


def test_compatible_nominal_target_needs_no_artificial_wait_cycles():
    cfg = case_config()
    cfg['waves']['B'] = copy.deepcopy(cfg['waves']['A'])
    day = simulate_day(config=cfg,start='06:00',end='08:00')
    request = day.transition('06:16:15')
    assert request.status == 'SUCCESS'
    assert request.transition_duration_s == request.transition_cycles == 0
    assert request.decisions == []
    assert [s['green_s'] for s in request.final_state] == NOMINAL


def test_restore_is_transactional_when_maximum_cycles_is_insufficient():
    cfg = case_config()
    cfg['transition']['max_transition_cycles'] = 1
    day = recovery_day(cfg)
    before = list(day.cycles)
    request = day.transition('06:16:15')
    assert request.status == 'FAILED' and 'MAX_TRANSITION_CYCLES' in request.reason
    assert request.decisions == []
    assert day.cycles == before


def test_duration_and_offset_corrections_are_explicit_independent_objects():
    selected,duration = choose_nominal_green(58,60,140,3,.2,green_step_s=1)
    assert selected == 59
    assert asdict(duration) == dict(green_delta_s=1,red_delta_s=-1)
    correction = assess_phase_offset(0,57,140)
    assert not correction.achievable and correction.requested_s == 57 and correction.applied_s == 0


def test_nominal_recovery_uses_fastest_allowed_step_when_no_smoothing_cap():
    selected,_ = choose_nominal_green(49,60,140,3,.2)
    assert selected == 60
    selected,_ = choose_nominal_green(71,60,140,3,.2)
    assert selected == 60


@pytest.mark.parametrize('bad_maximum',(39,0,60.5,[60,40]))
def test_invalid_max_green_is_rejected(bad_maximum):
    cfg = case_config()
    cfg['transition']['max_green_s'] = bad_maximum
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_query_uses_physical_origin_for_left_censored_phase():
    day = simulate_day(config=case_config(),start='06:00',end='08:00')
    with tempfile.TemporaryDirectory() as root:
        run,_ = day.export(root)
        state = query_history_state(run,'06:00')[5]
        assert state['cycle_start_s'] == -27
        assert state['phase_elapsed_s'] == 27


def test_overnight_day_and_timestamp_queries():
    day = simulate_day(config=case_config(),start='22:00',end='06:00')
    query = day.state_at('00:15:00')
    assert query[0]['timestamp'] == '2026-10-03T00:15:00'
    assert query == day.state_at('2026-10-03T00:15:00')
    assert day.transition('00:15:00').status == 'FAILED'


def test_audit_padding_is_explicit_and_does_not_change_requested_end():
    day = simulate_day(config=case_config(),start='06:00',end='06:59:59')
    meta = day.metadata()
    assert meta['requested_end'] == '2026-10-02T06:59:59'
    assert day.total_s == 3640
    assert meta['audit_horizon_extension_s'] == 41
    assert all(frame['end_s']-frame['start_s'] == 140 for frame in day.frames)


def test_success_extends_day_for_one_hour_of_stable_nominal_operation():
    cfg = case_config()
    cfg['simulation']['min_duration_s'] = 0
    cfg['waves']['B'] = copy.deepcopy(cfg['waves']['A'])
    day = simulate_day(config=cfg,start='06:00',end='06:20')
    request = day.transition('06:19')
    assert request.status == 'SUCCESS'
    assert day.total_s-request.transition_end_s >= 3600
    assert day.metadata()['requested_end'] == '2026-10-02T06:20:00'


def test_verifier_rejects_false_success_and_keeps_target_independent():
    day = prepare_simulation(case_config())
    with tempfile.TemporaryDirectory() as root:
        run,_ = day.export(root)
        path = run/'run.json'
        metadata = json.loads(path.read_text(encoding='utf-8'))
        request = metadata['plan']['transitions'][0]
        request.update(status='SUCCESS',target_achievable=True,transition_complete=True)
        path.write_text(json.dumps(metadata),encoding='utf-8')
        (run/'transition_summary.json').write_text(json.dumps(metadata['plan']['transitions']),encoding='utf-8')
        with pytest.raises(ValueError,match='SUCCESS declarado'):
            verify_day_history(run)


def test_verifier_rejects_phase_sequence_and_physical_period_tampering():
    day = prepare_simulation(case_config())
    with tempfile.TemporaryDirectory() as root:
        run,_ = day.export(root)
        path = run/'states.csv'
        contents = path.read_text(encoding='utf-8')
        path.write_text(contents.replace(',yellow,',',red,',1),encoding='utf-8')
        with pytest.raises(ValueError,match='estados no coinciden'):
            verify_day_history(run)


def test_verifier_rejects_max_green_violation_in_saved_configuration():
    day = recovery_day()
    day.transition('06:16:15')
    with tempfile.TemporaryDirectory() as root:
        run,_ = day.export(root)
        path = run/'config.json'
        cfg = json.loads(path.read_text(encoding='utf-8'))
        cfg['transition']['max_green_s'] = [60,40,55,53,43,65]
        path.write_text(json.dumps(cfg),encoding='utf-8')
        with pytest.raises(ValueError,match='mínimos/máximos'):
            verify_day_history(run)


def test_multiple_requests_and_source_wave_mismatch_are_explicit():
    cfg = case_config()
    cfg['waves']['B'] = copy.deepcopy(cfg['waves']['A'])
    day = simulate_day(config=cfg,start='06:00',end='08:00')
    assert day.transition('06:16:15').status == 'SUCCESS'
    invalid = day.transition('06:20:00',from_wave='A',to_wave='B')
    assert invalid.status == 'FAILED' and 'SOURCE_WAVE_MISMATCH' in invalid.reason
    assert day.transition('06:25:00',from_wave='B',to_wave='A').status == 'SUCCESS'
    assert day.active_wave_at('06:30:00') == 'A'
    with pytest.raises(ValueError,match='orden cronológico'):
        day.transition('06:15:00')


def test_fractional_request_times_preserve_real_elapsed_instead_of_truncating():
    day = simulate_day(config=case_config(),start='06:00',end='08:00')
    state = day.state_at('2026-10-02T06:16:15.5')
    assert state[4]['phase'] == 'yellow' and state[4]['phase_elapsed_s'] == 1.5
    request = day.transition('06:16:15.5')
    assert request.transition_start_s == request.transition_end_s == 975.5
    assert request.initial_state == request.final_state == state
    with tempfile.TemporaryDirectory() as root:
        run,_ = day.export(root)
        queried = query_history_state(run,'06:16:15.5')
        assert queried[4]['phase_elapsed_s'] == 1.5
        assert queried[4]['timestamp'] == '2026-10-02T06:16:15.500000'
        assert verify_day_history(run)['invalid_physical_cycles'] == 0


def test_common_target_rotation_is_not_silently_applied_to_exact_offsets():
    cfg = case_config()
    cfg['transition']['optimize_target_phase'] = True
    cfg['waves']['B'] = dict(direction='up',speed_kmh=70,offsets_s=[(o+5)%140 for o in OFFSETS_A])
    day = prepare_simulation(cfg)
    assert day.requests[0].status == 'FAILED'
    assert day.waves['B'].offsets_s == [(o+5)%140 for o in OFFSETS_A]
    assert day.state_at('07:30')[0]['offset_s'] == 0


def test_imported_controller_order_does_not_mix_intersections_and_targets():
    cfg = case_config()
    nominal = simulate_day(config=cfg,start='06:00',end='08:00')
    imported = list(reversed(nominal.cycles))
    resumed = simulate_day(config=cfg,start='06:00',end='08:00',controller_cycles=imported)
    assert [s['intersection_id'] for s in resumed.state_at('06:16:15')] == [f'S{i}' for i in range(1,7)]
    result = resumed.transition('06:16:15')
    assert result.status == 'FAILED'
    assert [s['offset_s'] for s in result.initial_state] == OFFSETS_A
