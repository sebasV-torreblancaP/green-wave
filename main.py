import argparse
import json
import math
from pathlib import Path

from green_wave import whole_seconds
from visualization import plot_day_timeline, plot_day_transition_metrics
from history import print_audit
from simulation import prepare_simulation

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'config.json'


def load_config(path=CONFIG):
    with Path(path).open(encoding='utf-8') as f:
        return json.load(f)


def print_plan(title, intersections, offsets, speed):
    print(f'\n{title}\n' + '-'*52)
    print(f'Velocidad: {speed:.2f} km/h')
    for inter, offset in zip(intersections, offsets):
        print(f'{inter.id}: offset = {offset:7d} s')


def validate_config(cfg):
    identifiers = [x['id'] for x in cfg['intersections']]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Cada intersección debe tener un id único para identificar su histórico.')
    for key in ('common_cycle_s', 'yellow_s'):
        whole_seconds(cfg['cycle'][key], f'cycle.{key}')
    for value in cfg['cycle']['green_base_s']:
        whole_seconds(value, 'cycle.green_base_s')
    for value in cfg['initial_offsets_s']:
        whole_seconds(value, 'initial_offsets_s')
    for key in ('min_green_s', 'min_red_s', 'green_step_s', 'min_down_band_s'):
        value = whole_seconds(cfg['transition'].get(key, 1), f'transition.{key}')
        if value <= 0:
            raise ValueError(f'transition.{key} debe ser positivo.')
    whole_seconds(cfg['simulation'].get('vehicle_start_offset_s',0), 'simulation.vehicle_start_offset_s')
    duration = whole_seconds(cfg['simulation'].get('min_duration_s', 0), 'simulation.min_duration_s')
    if duration < 0:
        raise ValueError('simulation.min_duration_s debe ser no negativo.')
    cycle, yellow = int(cfg['cycle']['common_cycle_s']), int(cfg['cycle']['yellow_s'])
    greens = cfg['cycle']['green_base_s']
    distances = [float(i['distance_from_s1_m']) for i in cfg['intersections']]
    if len(distances) < 2 or distances[0] != 0 or any(b <= a for a, b in zip(distances, distances[1:])):
        raise ValueError('Configura al menos dos distancias crecientes, empezando en 0 m.')
    if len(greens) != len(distances) or len(cfg['initial_offsets_s']) != len(distances):
        raise ValueError('green_base_s e initial_offsets_s deben tener un valor por semáforo.')
    fraction = float(cfg['transition']['max_green_change_fraction_per_cycle'])
    if cycle <= 0 or yellow < 0 or not 0 < fraction < 1:
        raise ValueError('Ciclo > 0, amarillo >= 0 y fracción de corrección entre 0 y 1.')
    min_green, min_red = (cfg['transition'].get('min_green_s', 1), cfg['transition'].get('min_red_s', 1))
    if any(g < min_green or cycle-g-yellow < min_red for g in greens):
        raise ValueError('El verde y el rojo base deben respetar min_green_s y min_red_s.')
    maximum = cfg['transition'].get('max_green_s',cycle-yellow-min_red)
    maxima = maximum if isinstance(maximum,list) else [maximum]*len(greens)
    if len(maxima) != len(greens):
        raise ValueError('max_green_s debe tener un valor por intersección.')
    for g,maximum in zip(greens,maxima):
        maximum = whole_seconds(maximum,'max_green_s')
        if maximum < min_green or g > maximum:
            raise ValueError('El verde nominal debe respetar max_green_s.')
    numeric = [cycle, yellow, fraction, min_green, min_red, *distances, *greens,
               *cfg['initial_offsets_s'], cfg['simulation'].get('vehicle_start_offset_s',0),
               cfg['corridor']['speed_up_kmh'], cfg['corridor']['speed_down_kmh']]
    if not all(math.isfinite(float(v)) for v in numeric):
        raise ValueError('Las entradas numéricas deben ser finitas.')
    if not isinstance(cfg['transition'].get('optimize_target_phase', True), bool):
        raise ValueError('optimize_target_phase debe ser true o false.')
    for key in ('speed_up_kmh', 'speed_down_kmh'):
        if cfg['corridor'][key] <= 0:
            raise ValueError(f'{key} debe ser mayor que cero.')
    for key in ('cycles_up', 'cycles_down', 'trajectories_per_cycle'):
        if key in ('cycles_up','cycles_down') and key not in cfg['simulation']:
            continue
        value = cfg['simulation'].get(key, 5 if key == 'trajectories_per_cycle' else 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f'{key} debe ser un entero positivo.')
    maximum = cfg['transition']['max_transition_cycles']
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
        raise ValueError('max_transition_cycles debe ser un entero positivo.')
    if cfg['corridor'].get('up_offsets_mode', 'calculated') not in ('calculated', 'manual'):
        raise ValueError('up_offsets_mode debe ser calculated o manual.')


def main():
    parser = argparse.ArgumentParser(description='Simulación diaria de Waves nominales con ciclo físico fijo')
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--no-show', action='store_true')
    parser.add_argument('--duration-s', type=int, help='Horizonte mínimo en segundos')
    parser.add_argument('--start',help='Inicio del día HH:MM[:SS]')
    parser.add_argument('--end',help='Fin del día HH:MM[:SS]')
    parser.add_argument('--transition-time',help='Hora arbitraria de solicitud HH:MM[:SS]')
    parser.add_argument('--at',help='Consultar estado real a esta hora')
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.duration_s is not None:
        cfg['simulation']['min_duration_s'] = args.duration_s
    cfg.setdefault('day',{})
    for key,value in (('start',args.start),('end',args.end),('transition_time',args.transition_time)):
        if value is not None:
            cfg['day'][key] = value
    validate_config(cfg)
    day = prepare_simulation(cfg)
    print('\n=== GREEN WAVE: SIMULACIÓN DIARIA ===')
    print(f'Ciclo físico: {day.cycle_s} s; ámbar: {day.amber_s} s; VERDE -> AMBAR -> ROJO.')
    for name,plan in day.waves.items():
        print_plan(f'WAVE {name} (objetivo independiente)',day.intersections,plan.offsets_s,plan.speed_kmh)
    for request in day.requests:
        print(f'\nSolicitud {request.from_wave} -> {request.to_wave} a {day.timestamp(request.transition_start_s)}')
        print(f'{request.status}: {request.reason}')
        print(f'Duración: {request.transition_duration_s} s; ciclos de ajuste: {request.transition_cycles}.')
        for s in request.initial_state:
            phase_label = {'green':'VERDE','yellow':'ÁMBAR','red':'ROJO'}[s['phase']]
            print(f"{s['intersection_id']}: {phase_label}, {s['phase_elapsed_s']} s desde el inicio de fase.")
    run_dir,audit = day.export(ROOT/'historico')
    print_audit(run_dir, audit)
    from verify_fixed_cycle import verify_fixed_cycle_history
    proof = verify_fixed_cycle_history(run_dir)
    print(f'Verificación física y nominal: {proof}')
    plot_day_timeline(day,ROOT/'green_wave.png',show=not args.no_show)
    plot_day_timeline(day,ROOT/'day_transition_detail.png',show=not args.no_show,zoom=True)
    plot_day_transition_metrics(day,ROOT/'transition.png',show=not args.no_show)
    import shutil
    for name in ('green_wave.png','day_transition_detail.png','transition.png'):
        shutil.copy2(ROOT/name,run_dir/name)
    if args.at:
        print(json.dumps(day.state_at(args.at),indent=2,ensure_ascii=False))
    return 2 if any(r.status == 'FAILED' for r in day.requests) else 0


if __name__ == '__main__':
    raise SystemExit(main())
