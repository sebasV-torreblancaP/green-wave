"""Verificación independiente del día, de la factibilidad y de la restauración."""
import json
from datetime import datetime,timedelta
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path

from history import audit_history,read_csv


def require(value,message):
    if not value:
        raise ValueError(message)


def snapshot(rows,t,cycle):
    result = []
    for identity in dict.fromkeys(r['intersection_id'] for r in rows):
        matching = [r for r in rows if r['intersection_id'] == identity and r['start_s'] <= t < r['end_s']]
        require(len(matching) == 1,f'{identity}: estado ambiguo o ausente a {t} s.')
        r = matching[0]
        ge,ae = r['start_s']+r['green_s'],r['start_s']+r['green_s']+r['yellow_s']
        phase,a,b = ('green',r['start_s'],ge) if t < ge else ('yellow',ge,ae) if t < ae else ('red',ae,r['end_s'])
        offset = r['start_s'] % cycle
        result.append(dict(intersection_id=identity,time_s=t,cycle_id=(r['start_s']-offset)//cycle+1,
                           phase=phase,phase_elapsed_s=t-a,phase_start_s=a,phase_end_s=b,
                           cycle_start_s=r['start_s'],cycle_end_s=r['end_s'],green_start_s=r['start_s'],
                           green_end_s=ge,amber_start_s=ge,amber_end_s=ae,red_start_s=ae,red_end_s=r['end_s'],
                           green_s=r['green_s'],amber_s=r['yellow_s'],red_s=r['red_s'],offset_s=offset))
    return result


def reconstruct_events(rows,total):
    events = []
    for r in rows:
        t = r['start_s']
        for phase in ('green','yellow','red'):
            duration = r[phase+'_s']
            a,b = max(0,t),min(total,t+duration)
            if b > a:
                events.append(dict(intersection_id=r['intersection_id'],state=phase,start_s=a,end_s=b,
                                   duration_s=b-a,stages=r['stage'],left_censored=int(a != t),
                                   right_censored=int(b != t+duration)))
            t += duration
    return events


def verify_day_history(run_directory):
    root = Path(run_directory)
    cfg = json.loads((root/'config.json').read_text(encoding='utf-8'))
    run = json.loads((root/'run.json').read_text(encoding='utf-8'))
    plan,total = run['plan'],run['total_time_s']
    cycle,amber = cfg['cycle']['common_cycle_s'],cfg['cycle']['yellow_s']
    require(plan['model'] == 'day_fixed_physical_cycles','Modelo diario incorrecto.')
    require(plan['nominal_green_s'] == cfg['cycle']['green_base_s'],'Se sobrescribieron los verdes nominales.')
    nominal = plan['nominal_green_s']
    require(plan['nominal_red_s'] == [cycle-g-amber for g in nominal],'Rojos nominales incorrectos.')
    require(total % cycle == 0 and total >= plan['requested_duration_s'],'Horizonte truncado o rejilla parcial.')
    require(plan['audit_horizon_extension_s'] == total-plan['requested_duration_s'],'Extensión de horizonte oculta.')
    cycle_fields = ('start_s','end_s','duration_s','green_s','yellow_s','red_s')
    rows = read_csv(root/'controller_cycles.csv',cycle_fields)
    baseline = read_csv(root/'baseline_controller_cycles.csv',cycle_fields)
    state_fields = ('start_s','end_s','duration_s','left_censored','right_censored')
    states = read_csv(root/'states.csv',state_fields)
    baseline_states = read_csv(root/'baseline_states.csv',state_fields)
    identities = [x['id'] for x in cfg['intersections']]
    require({r['intersection_id'] for r in rows} == set(identities),'Controladores faltantes o desconocidos.')
    limits = cfg['transition']
    commands = {(d['intersection_id'],d['time_s']):d for request in plan['transitions'] for d in request['decisions']}
    for dataset in (rows,baseline):
        for i,identity in enumerate(identities):
            own = sorted((r for r in dataset if r['intersection_id'] == identity),key=lambda r:r['start_s'])
            require(own and own[0]['start_s'] <= 0 and own[-1]['end_s'] >= total,f'{identity}: horizonte físico incompleto.')
            allowance = int((Decimal(nominal[i])*Decimal(str(limits['max_green_change_fraction_per_cycle']))).to_integral_value(rounding=ROUND_FLOOR))
            maximum = limits.get('max_green_s',cycle-amber-limits.get('min_red_s',1))
            maximum = maximum[i] if isinstance(maximum,list) else maximum
            for previous,current in zip(own,own[1:]):
                require(previous['end_s'] == current['start_s'] and current['start_s']-previous['start_s'] == cycle,
                        f'{identity}: ciclo discontinuo o inicio desplazado.')
                require(abs(current['green_s']-previous['green_s']) <= allowance,f'{identity}: cambio por ciclo fuera del límite nominal.')
                if dataset is rows and (identity,current['start_s']) in commands:
                    require(abs(current['green_s']-previous['green_s']) <= limits.get('green_step_s',allowance),
                            f'{identity}: cambio de transición mayor al paso permitido.')
            for r in own:
                require(r['duration_s'] == r['end_s']-r['start_s'] == r['green_s']+r['yellow_s']+r['red_s'] == cycle,
                        f'{identity}: ciclo físico inválido.')
                require(r['yellow_s'] == amber,f'{identity}: ámbar incorrecto.')
                require(limits.get('min_green_s',1) <= r['green_s'] <= maximum and r['red_s'] >= limits.get('min_red_s',1),
                        f'{identity}: fase fuera de los mínimos/máximos.')
                require(abs(r['green_s']-nominal[i]) <= allowance,f'{identity}: desviación nominal fuera del límite.')
            if plan['initial_state_source'] == 'nominal_wave':
                offset = plan['waves'][plan['initial_wave']]['offsets_s'][i]
                require(all(r['start_s'] % cycle == offset for r in own),f'{identity}: offset inicial alterado.')
                if dataset is baseline:
                    require(all(r['green_s'] == nominal[i] and r['red_s'] == plan['nominal_red_s'][i] for r in own),
                            'El histórico inicial del día no conserva el reparto nominal.')
    require(reconstruct_events(rows,total) == states,'Los estados no coinciden con las fases físicas programadas.')
    require(reconstruct_events(baseline,total) == baseline_states,'El histórico nominal previo no es reconstruible.')
    summaries = json.loads((root/'transition_summary.json').read_text(encoding='utf-8'))
    require(summaries == plan['transitions'],'Métricas de transición contradictorias.')
    physical = {(r['intersection_id'],r['start_s']):r for r in rows}
    baseline_map = {(r['intersection_id'],r['start_s']):r for r in baseline}
    success_ends = []
    statuses = []
    previous_start = -1
    active_wave = plan['initial_wave']
    for request in summaries:
        t,end = request['transition_start_s'],request['transition_end_s']
        require(0 <= t < plan['requested_duration_s'] and t >= previous_start,'Solicitud fuera del día o desordenada.')
        previous_start = t
        statuses.append(request['status'])
        observed_initial = snapshot(rows,t,cycle)
        # Una orden que entra exactamente en t puede modificar su reparto;
        # el estado previo está en el baseline si es la primera solicitud.
        if request is summaries[0]:
            observed_initial = snapshot(baseline,t,cycle)
        for recorded,observed in zip(request['initial_state'],observed_initial):
            require(all(recorded[k] == v for k,v in observed.items()),'El estado inicial no procede del histórico real.')
        target_offsets = plan['waves'][request['to_wave']]['offsets_s']
        errors = []
        for i,(s,correction) in enumerate(zip(request['initial_state'],request['offset_corrections'])):
            error = (target_offsets[i]-s['offset_s']) % cycle
            if error > cycle//2:
                error -= cycle
            errors.append(error)
            require(correction['requested_s'] == error and correction['applied_s'] == 0 and correction['achievable'] == (error == 0),
                    'La corrección de offset declarada oculta un desplazamiento físico.')
            target = request['target_state'][i]
            require(target['offset_s'] == target_offsets[i] and target['green_s'] == nominal[i]
                    and target['amber_s'] == amber and target['red_s'] == cycle-nominal[i]-amber,
                    'La Wave objetivo o sus duraciones nominales se sustituyeron.')
        require(request['transition_duration_s'] == end-t,'Duración de transición incorrecta.')
        final = snapshot(rows,end,cycle)
        for recorded,observed in zip(request['final_state'],final):
            require(all(recorded[k] == v for k,v in observed.items()),'Estado final incorrecto.')
        if request['status'] == 'SUCCESS':
            require(not any(errors) and request['target_achievable'] and request['transition_complete'],
                    'SUCCESS declarado sin alcanzar los offsets objetivo.')
            require(request['from_wave'] == active_wave,'SUCCESS desde una Wave que no estaba activa.')
            require(all(s['offset_s'] == target_offsets[i] and s['green_s'] == nominal[i]
                        and s['amber_s'] == amber and s['red_s'] == cycle-nominal[i]-amber for i,s in enumerate(final)),
                    'No se restauró exactamente la configuración nominal.')
            require(total-end >= max(3600,cfg.get('day',{}).get('post_transition_s',3600)),
                    'Falta al menos una hora estable después de completar la transición.')
            next_request = next((r['transition_start_s'] for r in summaries if r['transition_start_s'] > t),total)
            for i,identity in enumerate(identities):
                require(all(r['green_s'] == nominal[i] and r['red_s'] == cycle-nominal[i]-amber
                            for r in rows if r['intersection_id'] == identity and r['end_s'] > end and r['start_s'] < next_request),
                        'El reparto volvió a modificarse después de completar la transición.')
            success_ends.append(end)
            active_wave = request['to_wave']
        else:
            require(request['status'] == 'FAILED' and not request['transition_complete']
                    and not request['target_achievable'] and end == t and not request['decisions']
                    and request['transition_cycles'] == 0,'Transición fallida representada como cambios físicos.')
            if request is summaries[0]:
                next_request = next((r['transition_start_s'] for r in summaries if r['transition_start_s'] > t),total)
                for key,r in physical.items():
                    if r['start_s'] < next_request:
                        b = baseline_map[key]
                        require(all(r[k] == b[k] for k in cycle_fields),'Una solicitud fallida alteró el controlador.')
        for decision in request['decisions']:
            identity,stamp = decision['intersection_id'],decision['time_s']
            require(stamp >= t and (identity,stamp) in physical,'Orden fuera de un inicio físico de ciclo.')
            row = physical[identity,stamp]
            adjustment = decision['phase_duration_adjustment']
            require(row['green_s'] == decision['green_s'] and row['red_s'] == decision['red_s']
                    and row['yellow_s'] == decision['amber_s'],'Orden de fase no ejecutada en el histórico.')
            require(adjustment['green_delta_s'] == decision['green_s']-decision['green_before_s']
                    and adjustment['red_delta_s'] == -adjustment['green_delta_s'],'Compensación de rojo incorrecta.')
            require(abs(decision['green_error_s']) < abs(decision['green_error_before_s']),
                    'El ajuste no reduce el error: se añadieron ciclos de espera o cambios innecesarios.')
            correction = decision['phase_offset_correction']
            require(correction['applied_s'] == 0 and correction['requested_s'] == 0,
                    'Se asignó artificialmente el offset objetivo.')
    # Verifica además las filas ricas de fases y sus timestamps sin usar el productor.
    integer_fields = ('time_s','cycle_id','phase_elapsed_s','phase_start_s','phase_end_s','visible_end_s',
                      'green_start_s','green_end_s','amber_start_s','amber_end_s','red_start_s','red_end_s',
                      'green_duration','amber_duration','red_duration','offset')
    rich = read_csv(root/'phase_history.csv',integer_fields)
    require(len(rich) == len(states),'Fases faltantes en el histórico detallado.')
    origin = datetime.fromisoformat(plan['simulation_start'])
    for detailed,event in zip(rich,states):
        raw = physical[detailed['intersection'],detailed['green_start_s']]
        mapped_phase = 'yellow' if detailed['phase'] == 'amber' else detailed['phase']
        require(mapped_phase == event['state'] and detailed['time_s'] == event['start_s']
                and detailed['visible_end_s'] == event['end_s'],'Fases detalladas contradictorias.')
        require(detailed['green_duration'] == raw['green_s'] and detailed['amber_duration'] == raw['yellow_s']
                and detailed['red_duration'] == raw['red_s'],'Duraciones detalladas incorrectas.')
        boundaries = dict(green_start=raw['start_s'],green_end=raw['start_s']+raw['green_s'],
                          amber_start=raw['start_s']+raw['green_s'],
                          amber_end=raw['start_s']+raw['green_s']+raw['yellow_s'],
                          red_start=raw['start_s']+raw['green_s']+raw['yellow_s'],red_end=raw['end_s'])
        require(all(detailed[key+'_s'] == value and detailed[key] ==
                    (origin+timedelta(seconds=value)).isoformat()
                    for key,value in boundaries.items()),'Límites de fase detallados incorrectos.')
        require(detailed['phase_start_s'] == boundaries[detailed['phase']+'_start']
                and detailed['phase_end_s'] == boundaries[detailed['phase']+'_end']
                and detailed['offset'] == raw['start_s'] % cycle
                and detailed['cycle_id'] == (raw['start_s']-detailed['offset'])//cycle+1,
                'Origen físico o ciclo_id del histórico detallado incorrecto.')
        require(detailed['timestamp'] == (origin+timedelta(seconds=detailed['time_s'])).isoformat()
                and detailed['phase_elapsed_s'] == detailed['time_s']-detailed['phase_start_s'],
                'Timestamp o tiempo transcurrido de fase incorrecto.')
    audit = audit_history(root)
    require(audit['all_observed_cycles_constant'] and audit['global_windows_match_plan']
            and not any(audit[k] for k in ('sequence_issues','phase_issues','structural_issues','frame_issues')),
            'La auditoría existente detecta un fallo físico.')
    measured = read_csv(root/'cycles.csv',('start_green_s','next_green_s','duration_s','green_s','yellow_s','red_s'))
    require(all(r['next_green_s']-r['start_green_s'] == r['green_s']+r['yellow_s']+r['red_s'] == cycle
                and r['yellow_s'] == amber for r in measured),'cycles.csv no conserva períodos y fases nominales.')
    last = [max((r for r in rows if r['intersection_id'] == identity),key=lambda r:r['start_s']) for identity in identities]
    proof = dict(total_time_s=total,physical_cycle_s=cycle,amber_s=amber,controller_cycles=len(rows),
                 observed_cycles=len(measured),invalid_physical_cycles=0,sequence_issues=0,
                 wrong_amber_cycles=0,min_green_violations=0,max_green_violations=0,min_red_violations=0,
                 green_limits_valid=True,nominal_restored_after_success=True if success_ends else None,
                 final_greens_nominal=all(r['green_s'] == nominal[i] for i,r in enumerate(last)),
                 final_reds_nominal=all(r['red_s'] == cycle-nominal[i]-amber for i,r in enumerate(last)),
                 transition_statuses=statuses,target_offsets_reached=all(s == 'SUCCESS' for s in statuses) if statuses else None,
                 nominal_green_s=nominal,final_green_s=[r['green_s'] for r in last],
                 final_offsets_s=[r['start_s'] % cycle for r in last],
                 stable_after_success_s=[total-end for end in success_ends])
    (root/'physical_verification.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    return proof
