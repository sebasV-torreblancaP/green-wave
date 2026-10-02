"""Preparación común para las dos vistas y la verificación del plan final."""
import math

from green_wave import (Intersection, WavePlan, calculate_wave_plan,
                        find_down_green_target, transition_to_target_offsets)


def prepare_band_simulation(cfg):
    """Compatibilidad para ensayos antiguos por banda; nunca es el objetivo diario."""
    cycle = int(cfg['cycle']['common_cycle_s'])
    yellow = int(cfg['cycle']['yellow_s'])
    greens = [int(g) for g in cfg['cycle']['green_base_s']]
    intersections = [Intersection(x['id'], float(x['distance_from_s1_m'])) for x in cfg['intersections']]
    corridor, limits, sim = cfg['corridor'], cfg['transition'], cfg['simulation']
    up = calculate_wave_plan(intersections, cycle, corridor['speed_up_kmh'],
                             'up', cfg['initial_offsets_s'][0])
    if corridor.get('up_offsets_mode', 'calculated') == 'manual':
        up = WavePlan('up', corridor['speed_up_kmh'], [o % cycle for o in cfg['initial_offsets_s']])
    ideal_down = calculate_wave_plan(intersections, cycle, corridor['speed_down_kmh'], 'down', up.offsets_s[0])
    coordination = find_down_green_target(intersections, up.offsets_s, greens, cycle,
                                          yellow, corridor['speed_down_kmh'],
                                          limits.get('min_red_s', 1), limits.get('min_down_band_s', 1))
    if coordination['suggested_fraction'] > limits['max_green_change_fraction_per_cycle']:
        # Comparación final entera, también admite una fracción configurada
        # entre el valor exacto y su sugerencia redondeada hacia arriba.
        from decimal import Decimal, ROUND_FLOOR
        if any(target-base > int((Decimal(base)*Decimal(str(limits['max_green_change_fraction_per_cycle']))).to_integral_value(rounding=ROUND_FLOOR))
               for target, base in zip(coordination['target_green_s'], greens)):
            raise ValueError('BAJADA inalcanzable con el límite de verde actual. '
                             f"Mínimo para una banda de {coordination['min_band_s']} s: "
                             f"{coordination['minimum_fraction']}; configura "
                             f"max_green_change_fraction_per_cycle={coordination['suggested_fraction']}.")
    transition = transition_to_target_offsets(
        up.offsets_s, up.offsets_s, greens, cycle,
        max_change_fraction=limits['max_green_change_fraction_per_cycle'],
        max_cycles=limits['max_transition_cycles'], yellow_s=yellow,
        min_green_s=limits.get('min_green_s', 1), min_red_s=limits.get('min_red_s', 1),
        target_green_s=coordination['target_green_s'], green_step_s=limits.get('green_step_s', 1))
    down = WavePlan('down', corridor['speed_down_kmh'], up.offsets_s.copy())
    cycles_up, cycles_down = sim['cycles_up'], sim['cycles_down']
    minimum_cycles = math.ceil(sim.get('min_duration_s', 0)/cycle)
    cycles_down = max(cycles_down, minimum_cycles-cycles_up-transition.cycles_used)
    sim['cycles_down'] = cycles_down  # El snapshot contiene el horizonte realmente usado.
    return dict(intersections=intersections, cycle=cycle, yellow=yellow, greens=greens,
                up_plan=up, down_plan=down, ideal_down_plan=ideal_down,
                transition=transition, coordination=coordination,
                cycles_up=cycles_up, cycles_down=cycles_down)


def prepare_simulation(cfg):
    """Genera el día nominal, solicita la Wave exacta y conserva el resultado."""
    from day_simulation import simulate_day
    settings = cfg.get('day',{})
    day = simulate_day(start=settings.get('start','06:00'),end=settings.get('end','22:00'),
                       wave=settings.get('initial_wave','A'),config=cfg)
    requests = settings.get('requests')
    if requests is None:
        requests = [dict(time=settings.get('transition_time','13:37:24'),
                         from_wave=settings.get('initial_wave','A'),to_wave=settings.get('target_wave','B'))]
    for request in requests:
        day.transition(request['time'],request.get('from_wave',day.active_wave_at(request['time'])),request['to_wave'])
    return day.simulate_remaining_day()
