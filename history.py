"""Exportación persistente y auditoría independiente de los estados guardados."""
import argparse
import csv
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

FRAME_FIELDS = ('intersection_id', 'global_cycle', 'stage', 'start_s', 'end_s',
                'offset_s', 'green_s', 'yellow_s', 'red_s')
STATE_FIELDS = ('intersection_id', 'state', 'start_s', 'end_s', 'duration_s',
                'stages', 'left_censored', 'right_censored')
CYCLE_FIELDS = ('intersection_id', 'cycle_index', 'start_green_s', 'next_green_s',
                'duration_s', 'nominal_cycle_s', 'deviation_s', 'constant',
                'green_s', 'yellow_s', 'red_s', 'stages')


def write_csv(path, fields, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path, integer_fields):
    with Path(path).open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in integer_fields:
            row[field] = int(row[field])  # Rechaza tiempos fraccionarios en el archivo.
    return rows


def audit_history(run_dir):
    """Relee CSV en disco: no toma como evidencia las duraciones del plan."""
    run_dir = Path(run_dir)
    config = json.loads((run_dir / 'config.json').read_text(encoding='utf-8'))
    metadata = json.loads((run_dir / 'run.json').read_text(encoding='utf-8'))
    nominal, total = int(config['cycle']['common_cycle_s']), metadata['total_time_s']
    yellow = int(config['cycle']['yellow_s'])
    states = read_csv(run_dir / 'states.csv',
                      ('start_s', 'end_s', 'duration_s', 'left_censored', 'right_censored'))
    frames = read_csv(run_dir / 'frames.csv',
                      ('global_cycle', 'start_s', 'end_s', 'offset_s', 'green_s', 'yellow_s', 'red_s'))
    cycles, sequence_issues, phase_issues, summaries = [], [], [], []
    structural_issues, frame_issues = [], []
    expected_order = {'green': 'yellow' if yellow else 'red', 'yellow': 'red', 'red': 'green'}
    for inter in config['intersections']:
        identity = inter['id']
        rows = sorted((row for row in states if row['intersection_id'] == identity),
                      key=lambda row: row['start_s'])
        base = int(config['cycle']['green_base_s'][config['intersections'].index(inter)])
        fraction = Decimal(str(config['transition'].get('max_green_change_fraction_per_cycle', 0.2)))
        limit = int((Decimal(base) * fraction).to_integral_value(rounding=ROUND_FLOOR))
        green_bounds = (max(int(config['transition'].get('min_green_s', 1)), base - limit),
                        min(nominal - yellow - int(config['transition'].get('min_red_s', 1)), base + limit))
        previous_end = 0
        for index, row in enumerate(rows):
            if (row['start_s'] != previous_end or row['end_s'] <= row['start_s'] or
                    row['duration_s'] != row['end_s'] - row['start_s'] or
                    row['state'] not in expected_order):
                structural_issues.append(dict(intersection_id=identity, start_s=row['start_s']))
            previous_end = row['end_s']
            if index:
                previous = rows[index - 1]
                if expected_order.get(previous['state']) != row['state']:
                    sequence_issues.append(dict(intersection_id=identity, time_s=row['start_s'],
                                                previous=previous['state'], current=row['state']))
            if not row['left_censored'] and not row['right_censored']:
                minimum = int(config['transition'].get('min_green_s' if row['state'] == 'green'
                                                       else 'min_red_s', 1))
                reason = None
                if row['state'] == 'yellow' and row['duration_s'] != yellow:
                    reason = 'amarillo_observado_distinto_del_configurado'
                elif row['state'] in ('green', 'red') and row['duration_s'] < minimum:
                    reason = 'fase_observada_menor_al_minimo'
                if reason is None and row['state'] == 'green' and not green_bounds[0] <= row['duration_s'] <= green_bounds[1]:
                    reason = 'verde_observado_fuera_del_limite_base'
                if reason:
                    phase_issues.append(dict(intersection_id=identity, state=row['state'],
                                             start_s=row['start_s'], duration_s=row['duration_s'], reason=reason))
        if not rows or previous_end != total:
            structural_issues.append(dict(intersection_id=identity, reason='horizonte_incompleto'))
        own_frames = sorted((frame for frame in frames if frame['intersection_id'] == identity),
                            key=lambda frame: frame['start_s'])
        frame_end = 0
        for frame in own_frames:
            occupancy = {state: 0 for state in expected_order}
            for row in rows:
                overlap = max(0, min(row['end_s'], frame['end_s']) - max(row['start_s'], frame['start_s']))
                if row['state'] in occupancy:
                    occupancy[row['state']] += overlap
            if (frame['start_s'] != frame_end or frame['end_s'] - frame['start_s'] != nominal or
                    frame['green_s'] + frame['yellow_s'] + frame['red_s'] != nominal or
                    any(occupancy[state] != frame[state + '_s'] for state in occupancy)):
                frame_issues.append(dict(intersection_id=identity, global_cycle=frame['global_cycle']))
            frame_end = frame['end_s']
        if frame_end != total:
            frame_issues.append(dict(intersection_id=identity, reason='ventanas_incompletas'))
        # Inicios realmente observados, excluyendo el verde inicial parcial.
        starts = [row['start_s'] for row in rows if row['state'] == 'green' and not row['left_censored']]
        own_cycles = []
        for index, (start, end) in enumerate(zip(starts, starts[1:]), 1):
            durations = {state: 0 for state in expected_order}
            stages = []
            for row in rows:
                overlap = max(0, min(end, row['end_s']) - max(start, row['start_s']))
                if overlap:
                    if row['state'] in durations:
                        durations[row['state']] += overlap
            for frame in own_frames:
                if min(end, frame['end_s']) > max(start, frame['start_s']) and frame['stage'] not in stages:
                    stages.append(frame['stage'])
            observed = dict(intersection_id=identity, cycle_index=index, start_green_s=start,
                            next_green_s=end, duration_s=end - start, nominal_cycle_s=nominal,
                            deviation_s=end - start - nominal, constant=int(end - start == nominal),
                            green_s=durations['green'], yellow_s=durations['yellow'],
                            red_s=durations['red'], stages='|'.join(stages))
            own_cycles.append(observed)
            cycles.append(observed)
        durations = [row['duration_s'] for row in own_cycles]
        summaries.append(dict(intersection_id=identity, complete_cycles=len(durations),
                              nonconstant_cycles=sum(not row['constant'] for row in own_cycles),
                              min_cycle_s=min(durations) if durations else None,
                              max_cycle_s=max(durations) if durations else None))
    report = dict(nominal_cycle_s=nominal, measured_complete_cycles=len(cycles),
                  nonconstant_cycles=sum(not row['constant'] for row in cycles),
                  all_observed_cycles_constant=(bool(cycles) and all(row['constant'] for row in cycles)),
                  global_windows_match_plan=not frame_issues,
                  structural_issues=structural_issues, frame_issues=frame_issues,
                  sequence_issues=sequence_issues, phase_issues=phase_issues,
                  intersections=summaries,
                  definition='Ciclo observado: tiempo entre dos inicios consecutivos de verde. '
                             'Los extremos parciales del horizonte no se cuentan como ciclos completos.')
    write_csv(run_dir / 'cycles.csv', CYCLE_FIELDS, cycles)
    (run_dir / 'audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    lines = [f'Ciclo nominal: {nominal} s',
             f'Ciclos completos medidos: {len(cycles)}',
             f'Ciclos de duración distinta: {report["nonconstant_cycles"]}',
             f'Cambios de color fuera de secuencia: {len(sequence_issues)}',
             f'Fases fuera de duración/mínimos: {len(phase_issues)}', '',
             'Intersección | ciclos completos | distintos | mínimo(s) | máximo(s)']
    for item in summaries:
        lines.append(f'{item["intersection_id"]} | {item["complete_cycles"]} | '
                     f'{item["nonconstant_cycles"]} | {item["min_cycle_s"]} | {item["max_cycle_s"]}')
    lines += ['', report['definition'],
              'La suma de las fases por ventana global no demuestra que los ciclos observados sean constantes.']
    (run_dir / 'audit.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


def export_history(root, config, frames, states, controller_cycles=None, plan_metadata=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run_dir = root / stamp
    run_dir.mkdir()
    (run_dir / 'config.json').write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (run_dir / 'run.json').write_text(json.dumps(dict(
        created_at_utc=stamp, total_time_s=max(row['end_s'] for row in frames),
        interval_convention='[start_s, end_s): inicio incluido, fin excluido',
        states_source='Eventos de ciclos locales explícitos.' if controller_cycles is not None
                      else 'Cronología común usada para dibujar ambas gráficas; colores contiguos unidos.',
        frames_source='Ocupación real de los eventos por ventana global.' if controller_cycles is not None
                      else 'Reparto programado por ventana global.',
        plan=plan_metadata,
    ), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_csv(run_dir / 'frames.csv', FRAME_FIELDS, frames)
    write_csv(run_dir / 'states.csv', STATE_FIELDS, states)
    if controller_cycles is not None:
        fields = ('intersection_id', 'start_s', 'end_s', 'duration_s', 'green_s',
                  'yellow_s', 'red_s', 'stage')
        write_csv(run_dir / 'controller_cycles.csv', fields, [dict(
            intersection_id=c.intersection_id, start_s=c.start_s, end_s=c.end_s,
            duration_s=c.duration_s, green_s=c.green_s, yellow_s=c.yellow_s,
            red_s=c.red_s, stage=c.stage) for c in controller_cycles])
    report = audit_history(run_dir)  # Verificación explícita de lo guardado.
    (root / 'latest.json').write_text(json.dumps({'run_directory': run_dir.name}, indent=2) + '\n', encoding='utf-8')
    return run_dir, report


def print_audit(run_dir, report):
    print(f'\nHistórico: {run_dir}')
    print(f'AUDITORÍA: {report["nonconstant_cycles"]} de {report["measured_complete_cycles"]} '
          f'ciclos observados difieren de {report["nominal_cycle_s"]} s.')
    print(f'Cambios de color fuera de secuencia: {len(report["sequence_issues"])}.')
    for row in report['intersections']:
        print(f'{row["intersection_id"]}: mínimo {row["min_cycle_s"]} s, máximo {row["max_cycle_s"]} s; '
              f'{row["nonconstant_cycles"]} ciclos distintos.')


def export_day_history(root, simulation):
    """Amplía la evidencia diaria sin cambiar las verificaciones de audit_history."""
    run, report = export_history(root,simulation.config,simulation.frames,simulation.states,
                                 controller_cycles=simulation.cycles,plan_metadata=simulation.metadata())
    fields = ('intersection_id','start_s','end_s','duration_s','green_s','yellow_s','red_s','stage')
    baseline = [dict(intersection_id=c.intersection_id,start_s=c.start_s,end_s=c.end_s,
                     duration_s=c.duration_s,green_s=c.green_s,yellow_s=c.yellow_s,red_s=c.red_s,stage=c.stage)
                for c in simulation.baseline_cycles]
    write_csv(run/'baseline_controller_cycles.csv',fields,baseline)
    write_csv(run/'baseline_states.csv',STATE_FIELDS,simulation.baseline_states)
    phase_rows = []
    for c in simulation.cycles:
        offset = c.start_s % simulation.cycle_s
        green_end = c.start_s+c.green_s
        amber_end = green_end+c.yellow_s
        boundaries = dict(green_start=c.start_s,green_end=green_end,amber_start=green_end,
                          amber_end=amber_end,red_start=amber_end,red_end=c.end_s)
        for phase,a,b in (('green',c.start_s,green_end),('amber',green_end,amber_end),('red',amber_end,c.end_s)):
            visible_start,visible_end = max(0,a),min(simulation.total_s,b)
            if visible_end <= visible_start:
                continue
            phase_rows.append(dict(timestamp=simulation.timestamp(visible_start),time_s=visible_start,
                intersection=c.intersection_id,cycle_id=(c.start_s-offset)//simulation.cycle_s+1,
                phase=phase,phase_elapsed_s=visible_start-a,phase_start_s=a,phase_end_s=b,
                visible_end_s=visible_end,offset=offset,
                green_duration=c.green_s,amber_duration=c.yellow_s,red_duration=c.red_s,
                stage=c.stage,**{key:simulation.timestamp(value) for key,value in boundaries.items()},
                **{key+'_s':value for key,value in boundaries.items()}))
    phase_fields = ('timestamp','time_s','intersection','cycle_id','phase','phase_elapsed_s',
                    'phase_start_s','phase_end_s','visible_end_s','green_start','green_end',
                    'amber_start','amber_end','red_start','red_end','green_start_s','green_end_s',
                    'amber_start_s','amber_end_s','red_start_s','red_end_s','green_duration',
                    'amber_duration','red_duration','offset','stage')
    write_csv(run/'phase_history.csv',phase_fields,phase_rows)
    transitions = []
    for request_id,request in enumerate(simulation.requests,1):
        corrections = {s['intersection_id']:c for s,c in zip(request.initial_state,request.offset_corrections)}
        for event,status in ((request.initial_state,'FAILED' if request.status == 'FAILED' else 'REQUESTED'),
                             (request.final_state,request.status)):
            if status == 'FAILED' and event is request.final_state:
                continue
            for s in event:
                correction = corrections[s['intersection_id']]
                i = next(i for i,x in enumerate(simulation.intersections) if x.id == s['intersection_id'])
                transitions.append(dict(request_id=request_id,timestamp=simulation.timestamp(s['time_s']),
                    time_s=s['time_s'],intersection=s['intersection_id'],cycle_id=s['cycle_id'],
                    phase=s['phase'],phase_elapsed_s=s['phase_elapsed_s'],green=s['green_s'],
                    amber=s['amber_s'],red=s['red_s'],offset=s['offset_s'],
                    target_offset=simulation.waves[request.to_wave].offsets_s[i],offset_error=correction['requested_s'],
                    green_error=simulation.nominal_green_s[i]-s['green_s'],duration_green_delta_s=0,
                    duration_red_delta_s=0,offset_requested_correction_s=correction['requested_s'],
                    offset_applied_correction_s=correction['applied_s'],status=status,reason=request.reason))
        for d in request.decisions:
            adjustment,correction = d['phase_duration_adjustment'],d['phase_offset_correction']
            transitions.append(dict(request_id=request_id,timestamp=simulation.timestamp(d['time_s']),
                time_s=d['time_s'],intersection=d['intersection_id'],
                cycle_id=(d['time_s']-d['offset_s'])//simulation.cycle_s+1,phase='green',phase_elapsed_s=0,
                green=d['green_s'],amber=d['amber_s'],red=d['red_s'],offset=d['offset_s'],
                target_offset=d['target_offset_s'],offset_error=d['offset_error_s'],green_error=d['green_error_s'],
                duration_green_delta_s=adjustment['green_delta_s'],duration_red_delta_s=adjustment['red_delta_s'],
                offset_requested_correction_s=correction['requested_s'],offset_applied_correction_s=correction['applied_s'],
                status='APPLIED',reason='Reevaluación local: minimizar error nominal y perturbación.'))
    transition_fields = ('request_id','timestamp','time_s','intersection','cycle_id','phase','phase_elapsed_s',
                         'green','amber','red','offset','target_offset','offset_error','green_error',
                         'duration_green_delta_s','duration_red_delta_s','offset_requested_correction_s',
                         'offset_applied_correction_s','status','reason')
    transitions.sort(key=lambda r:(r['time_s'],r['request_id'],r['intersection']))
    write_csv(run/'transitions.csv',transition_fields,transitions)
    (run/'transition_summary.json').write_text(json.dumps(simulation.metadata()['transitions'],indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return run,report


def query_history_state(run_directory, moment):
    """Consulta el CSV físico, no deduce estados desde ventanas globales."""
    from datetime import timedelta, time
    from continuous import LocalCycle,controller_state_at
    run = Path(run_directory)
    metadata = json.loads((run/'run.json').read_text(encoding='utf-8'))
    start = datetime.fromisoformat(metadata['plan']['simulation_start'])
    if isinstance(moment,(int,float)) and not isinstance(moment,bool):
        from green_wave import whole_seconds
        elapsed = whole_seconds(moment,'time_s')
    else:
        stamp = datetime.fromisoformat(moment) if 'T' in moment else datetime.combine(start.date(),time.fromisoformat(moment))
        if stamp < start and 'T' not in moment:
            stamp += timedelta(days=1)
        elapsed = int((stamp-start).total_seconds())
    if not 0 <= elapsed < metadata['total_time_s']:
        raise ValueError('Consulta fuera del horizonte del histórico.')
    rows = read_csv(run/'controller_cycles.csv',('start_s','green_s','yellow_s','red_s','end_s','duration_s'))
    cycles = [LocalCycle(r['intersection_id'],r['start_s'],r['green_s'],r['yellow_s'],r['red_s'],r['stage']) for r in rows]
    return [dict(s,timestamp=(start+timedelta(seconds=elapsed)).isoformat(timespec='seconds'))
            for s in controller_state_at(cycles,elapsed)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verificar de nuevo un histórico de estados guardado')
    parser.add_argument('run_directory', type=Path, nargs='?')
    parser.add_argument('--latest', action='store_true', help='Auditar la última ejecución del proyecto')
    parser.add_argument('--at', help='Consultar el estado real a una hora HH:MM:SS o timestamp ISO')
    args = parser.parse_args()
    if args.latest:
        root = Path(__file__).resolve().parent / 'historico'
        pointer = json.loads((root / 'latest.json').read_text(encoding='utf-8'))
        run_dir = root / pointer['run_directory']
    elif args.run_directory is not None:
        run_dir = args.run_directory
    else:
        parser.error('Indica una carpeta histórica o --latest.')
    if args.at:
        print(json.dumps(query_history_state(run_dir,args.at),indent=2,ensure_ascii=False))
    else:
        print_audit(run_dir, audit_history(run_dir))
