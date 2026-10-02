"""Cronología física: cada orden se aplica al empezar un ciclo local."""
import math

from continuous import LocalCycle, cycle_events


def frames_from_events(intersections, cycle, total_s, offsets, states, stage_at):
    """Ventanas observacionales, derivadas de eventos; no son órdenes de fase."""
    if total_s % cycle:
        raise ValueError('El horizonte de auditoría debe cubrir ventanas globales completas.')
    frames = []
    count = total_s//cycle
    for i, intersection in enumerate(intersections):
        own = [dict(intersection_id=intersection.id, global_cycle=k+1,
                    stage=stage_at(k*cycle), start_s=k*cycle, end_s=(k+1)*cycle,
                    offset_s=offsets[i], green_s=0, yellow_s=0, red_s=0)
               for k in range(count)]
        for row in states:
            if row['intersection_id'] != intersection.id:
                continue
            first, last = row['start_s']//cycle, (row['end_s']-1)//cycle
            for k in range(first, last+1):
                own[k][row['state']+'_s'] += min((k+1)*cycle,row['end_s'])-max(k*cycle,row['start_s'])
        frames.extend(own)
    return frames


def phase_segments(offset, green, yellow, cycle, start, end):
    """Fases de un plan estable; nunca se usa para recortar una transición."""
    for k in range(math.floor((start-offset)/cycle)-1, math.ceil((end-offset)/cycle)+1):
        origin = offset+k*cycle
        for phase, a, b in (('green', origin, origin+green),
                             ('yellow', origin+green, origin+green+yellow),
                             ('red', origin+green+yellow, origin+cycle)):
            a, b = max(start, a), min(end, b)
            if b > a:
                yield phase, a, b


def build_controller_cycles(intersections, cycle, yellow, greens, up_plan,
                            transition, cycles_up, cycles_down):
    """Inicios t[i,k] = offset[i] + k*C; G cambia, A fijo, R complemento."""
    if transition.cycle_s != cycle or transition.yellow_s != yellow:
        raise ValueError('La transición y el timeline deben usar el mismo ciclo y amarillo.')
    offsets = [o % cycle for o in up_plan.offsets_s]
    if (transition.final_offsets_s != offsets or
            any(row != offsets for row in transition.offset_history)):
        raise ValueError('El controlador de ciclo fijo no admite cambios de inicio de verde.')
    total_cycles = cycles_up+transition.cycles_used+cycles_down
    result = []
    final_greens = transition.final_green_s or greens
    for i, inter in enumerate(intersections):
        # Incluye ciclos reales que cruzan ambos extremos del horizonte.
        for c in range(-1, total_cycles):
            if c < cycles_up:
                stage, green = 'subida', greens[i]
            elif c < cycles_up+transition.cycles_used:
                stage, green = 'transicion', transition.green_history[c-cycles_up][i]
            else:
                stage, green = 'bajada', final_greens[i]
            result.append(LocalCycle(inter.id, offsets[i]+c*cycle, green,
                                     yellow, cycle-green-yellow, stage))
    return result


def build_timeline(intersections, cycle, yellow, greens, up_plan, transition,
                   cycles_up, cycles_down, return_cycles=False):
    """Exporta eventos continuos y su ocupación real por ventana global.

    Las ventanas son vistas de los eventos; no reprograman colores ni se
    presentan como ciclos locales. La auditoría sigue midiendo los verdes.
    """
    total_cycles = cycles_up+transition.cycles_used+cycles_down
    cycles = build_controller_cycles(intersections, cycle, yellow, greens,
                                     up_plan, transition, cycles_up, cycles_down)
    states = cycle_events(cycles, total_cycles*cycle, expected_cycle_s=cycle)
    frames = []
    for i, inter in enumerate(intersections):
        own = [row for row in states if row['intersection_id'] == inter.id]
        for c in range(total_cycles):
            start, end = c*cycle, (c+1)*cycle
            stage = ('subida' if c < cycles_up else
                     'transicion' if c < cycles_up+transition.cycles_used else 'bajada')
            occupancy = dict.fromkeys(('green', 'yellow', 'red'), 0)
            for row in own:
                occupancy[row['state']] += max(0, min(end, row['end_s'])-max(start, row['start_s']))
            frames.append(dict(intersection_id=inter.id, global_cycle=c+1,
                               stage=stage, start_s=start, end_s=end,
                               offset_s=up_plan.offsets_s[i] % cycle,
                               **{state+'_s': duration for state, duration in occupancy.items()}))
    return (frames, states, cycles) if return_cycles else (frames, states)
