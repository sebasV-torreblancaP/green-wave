"""Verificación independiente del CSV físico y las llegadas en BAJADA."""
import argparse
import json
import math
from decimal import Decimal, ROUND_FLOOR
from fractions import Fraction
from pathlib import Path

from history import audit_history, read_csv, write_csv


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_fixed_cycle_history(run_directory):
    root = Path(run_directory)
    cfg = json.loads((root/'config.json').read_text(encoding='utf-8'))
    metadata = json.loads((root/'run.json').read_text(encoding='utf-8'))
    plan = metadata['plan']
    if plan.get('model') == 'day_fixed_physical_cycles':
        from verify_day import verify_day_history
        return verify_day_history(root)
    cycle, yellow, total = cfg['cycle']['common_cycle_s'], cfg['cycle']['yellow_s'], metadata['total_time_s']
    rows = read_csv(root/'controller_cycles.csv', ('start_s', 'end_s', 'duration_s', 'green_s', 'yellow_s', 'red_s'))
    states = read_csv(root/'states.csv', ('start_s', 'end_s', 'duration_s', 'left_censored', 'right_censored'))
    identities = [x['id'] for x in cfg['intersections']]
    require({x['intersection_id'] for x in rows} == set(identities), 'Controladores faltantes o desconocidos.')
    limits = cfg['transition']
    reconstructed = []
    observed_pairs = 0
    for i, identity in enumerate(identities):
        own = sorted((r for r in rows if r['intersection_id'] == identity), key=lambda r: r['start_s'])
        base = cfg['cycle']['green_base_s'][i]
        allowance = int((Decimal(base)*Decimal(str(limits['max_green_change_fraction_per_cycle']))).to_integral_value(rounding=ROUND_FLOOR))
        require(own[0]['start_s'] <= 0 and own[-1]['end_s'] >= total, f'{identity}: horizonte incompleto.')
        for previous, current in zip(own, own[1:]):
            require(previous['end_s'] == current['start_s'], f'{identity}: discontinuidad física.')
            require(current['start_s']-previous['start_s'] == cycle, f'{identity}: inicios distintos de {cycle} s.')
            require(abs(current['green_s']-previous['green_s']) <= min(allowance, limits.get('green_step_s', 1)),
                    f'{identity}: cambio de verde por ciclo fuera del límite.')
        for r in own:
            require(r['duration_s'] == r['end_s']-r['start_s'] == r['green_s']+r['yellow_s']+r['red_s'] == cycle,
                    f'{identity}: ciclo físico incorrecto.')
            require(r['yellow_s'] == yellow and r['green_s'] >= limits.get('min_green_s', 1)
                    and r['red_s'] >= limits.get('min_red_s', 1), f'{identity}: mínimos o amarillo incorrectos.')
            require(abs(r['green_s']-base) <= allowance, f'{identity}: verde fuera del límite respecto a la base.')
            require(r['start_s'] % cycle == plan['final_offsets_s'][i], f'{identity}: inicio desplazado.')
            k = (r['start_s']-plan['up_offsets_s'][i])//cycle
            first, end = cfg['simulation']['cycles_up'], cfg['simulation']['cycles_up']+plan['transition_cycles']
            expected_stage = 'subida' if k < first else 'transicion' if k < end else 'bajada'
            require(r['stage'] == expected_stage, f'{identity}: etapa incorrecta.')
            target = plan['final_green_s'][i]
            if k < first:
                expected_green = base
            elif k < end:
                step = min(allowance, limits.get('green_step_s', 1))
                expected_green = base + (1 if target >= base else -1)*min(abs(target-base), (k-first+1)*step)
            else:
                expected_green = target
            require(r['green_s'] == expected_green, f'{identity}: orden de reparto incumplida.')
            t = r['start_s']
            for state in ('green', 'yellow', 'red'):
                duration = r[state+'_s']
                a, b = max(0, t), min(total, t+duration)
                if b > a:
                    reconstructed.append(dict(intersection_id=identity, state=state, start_s=a, end_s=b,
                                              duration_s=b-a, stages=r['stage'], left_censored=int(a != t),
                                              right_censored=int(b != t+duration)))
                t += duration
        starts = [r['start_s'] for r in states if r['intersection_id'] == identity
                  and r['state'] == 'green' and not r['left_censored']]
        require(all(b-a == cycle for a, b in zip(starts, starts[1:])), f'{identity}: eventos de verde incorrectos.')
        observed_pairs += max(0, len(starts)-1)
    require(reconstructed == states, 'states.csv no corresponde a las fases físicas programadas.')
    report = audit_history(root)
    require(report['all_observed_cycles_constant'] and report['global_windows_match_plan']
            and not any(report[k] for k in ('sequence_issues', 'phase_issues', 'structural_issues', 'frame_issues')),
            'La auditoría existente detecta un fallo.')
    measured = read_csv(root/'cycles.csv', ('start_green_s', 'next_green_s', 'duration_s', 'green_s', 'yellow_s', 'red_s'))
    require(len(measured) == observed_pairs and all(r['next_green_s']-r['start_green_s'] == cycle
            and r['green_s']+r['yellow_s']+r['red_s'] == cycle and r['yellow_s'] == yellow for r in measured),
            'cycles.csv no conserva los ciclos físicos y sus fases.')
    # Verifica toda la banda declarada con viajes racionales; no exige que la
    # llegada coincida con el inicio de verde. Nunca sustituye los offsets.
    band = Fraction(limits.get('min_down_band_s', 1))
    departure = Fraction(plan['coordination'].get('departure_exact_s', str(plan['coordination']['departure_s'])))
    speed = Fraction(str(cfg['corridor']['speed_down_kmh']))
    source = Fraction(str(cfg['intersections'][-1]['distance_from_s1_m']))
    for i, intersection in enumerate(cfg['intersections']):
        travel = (source-Fraction(str(intersection['distance_from_s1_m'])))*Fraction(18, 5)/speed
        phase = (departure+travel-plan['final_offsets_s'][i]) % cycle
        require(phase+band <= plan['final_green_s'][i], 'La banda declarada no llega íntegramente en verde.')
    # Comprueba además vehículos sobre los eventos guardados de la BAJADA estable.
    stable_start = (cfg['simulation']['cycles_up']+plan['transition_cycles'])*cycle + max(plan['final_offsets_s'])
    arrivals, vehicles = [], 0
    first_cycle = math.ceil((stable_start-departure)/cycle)
    max_travel = source*Fraction(18, 5)/speed
    for k in range(first_cycle, total//cycle+1):
        depart = k*cycle+departure+band/2
        if depart+max_travel >= total:
            continue
        vehicles += 1
        for intersection in cfg['intersections']:
            travel = (source-Fraction(str(intersection['distance_from_s1_m'])))*Fraction(18, 5)/speed
            arrival = depart+travel
            matching = [r for r in states if r['intersection_id'] == intersection['id']
                        and r['start_s'] <= arrival < r['end_s']]
            require(len(matching) == 1 and matching[0]['state'] == 'green', 'Vehículo BAJADA fuera del verde real.')
            arrivals.append(dict(vehicle=vehicles, intersection_id=intersection['id'],
                                 departure_s=float(depart), arrival_s=float(arrival), state='green'))
    require(vehicles > 0, 'Horizonte insuficiente para verificar un recorrido completo de BAJADA.')
    write_csv(root/'bajada_arrivals.csv', ('vehicle', 'intersection_id', 'departure_s', 'arrival_s', 'state'), arrivals)
    proof = dict(total_time_s=total, controller_cycles=len(rows), observed_cycles=len(measured),
                 all_cycles_140_s=(cycle == 140), physical_cycle_s=cycle,
                 sequence_valid=True, green_limits_valid=True, down_band_valid=True,
                 complete_down_vehicles=vehicles, ideal_down_offsets_reached=(plan['ideal_down_offsets_s'] == plan['final_offsets_s']))
    (root/'physical_verification.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_fixed_cycle_history(args.run_directory), indent=2))
