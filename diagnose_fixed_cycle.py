"""Diagnóstico de alcanzabilidad; no modifica el plan ni la auditoría."""
import json
import argparse
from decimal import Decimal, ROUND_FLOOR

from continuous import fixed_cycle_feasibility
from green_wave import Intersection, WavePlan, calculate_wave_plan, find_down_green_target
from main import load_config
from visualization import green_departure_windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.json')
    args = parser.parse_args()
    cfg = load_config(args.config)
    cycle = cfg['cycle']['common_cycle_s']
    intersections = [Intersection(x['id'], x['distance_from_s1_m'])
                     for x in cfg['intersections']]
    corridor = cfg['corridor']
    up = calculate_wave_plan(intersections, cycle, corridor['speed_up_kmh'],
                             'up', cfg['initial_offsets_s'][0])
    if corridor.get('up_offsets_mode') == 'manual':
        up = WavePlan('up', corridor['speed_up_kmh'],
                      [x % cycle for x in cfg['initial_offsets_s']])
    down = calculate_wave_plan(intersections, cycle, corridor['speed_down_kmh'],
                               'down', up.offsets_s[0])
    limits = cfg['transition']
    fraction = Decimal(str(limits['max_green_change_fraction_per_cycle']))
    maximum = [min(g + int((Decimal(g) * fraction).to_integral_value(rounding=ROUND_FLOOR)),
                   cycle - cfg['cycle']['yellow_s'] - limits.get('min_red_s', 1))
               for g in cfg['cycle']['green_base_s']]
    report = dict(
        up_offsets_s=up.offsets_s,
        down_offsets_s=down.offsets_s,
        fixed_green_start_feasibility=fixed_cycle_feasibility(
            up.offsets_s, down.offsets_s, cycle, limits.get('optimize_target_phase', True)),
        maximum_allowed_greens_s=maximum,
        down_departure_windows_with_fixed_starts=green_departure_windows(
            intersections, WavePlan('down', down.speed_kmh, up.offsets_s), maximum, cycle),
        minimum_down_band_variant=find_down_green_target(
            intersections, up.offsets_s, cfg['cycle']['green_base_s'], cycle,
            cfg['cycle']['yellow_s'], down.speed_kmh, limits.get('min_red_s', 1),
            limits.get('min_down_band_s', 1)),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
