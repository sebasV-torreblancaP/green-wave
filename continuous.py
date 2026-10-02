"""Conversión de ciclos locales explícitos a eventos, sin recortes por rejilla."""
from dataclasses import dataclass
from bisect import bisect_right

from green_wave import whole_seconds


@dataclass(frozen=True)
class LocalCycle:
    intersection_id: str
    start_s: int
    green_s: int
    yellow_s: int
    red_s: int
    stage: str

    def __post_init__(self):
        for key in ('start_s', 'green_s', 'yellow_s', 'red_s'):
            object.__setattr__(self, key, whole_seconds(getattr(self, key), key))
        if self.green_s <= 0 or self.yellow_s < 0 or self.red_s <= 0:
            raise ValueError('Cada ciclo requiere verde y rojo positivos; amarillo no negativo.')

    @property
    def end_s(self):
        return self.start_s + self.green_s + self.yellow_s + self.red_s

    @property
    def duration_s(self):
        return self.green_s + self.yellow_s + self.red_s


def controller_state_at(cycles, time_s):
    """Estado real [inicio,fin), usando el origen físico incluso si es negativo."""
    time_s = whole_seconds(time_s, 'time_s')
    states = []
    for identity in dict.fromkeys(c.intersection_id for c in cycles):
        own = sorted((c for c in cycles if c.intersection_id == identity), key=lambda c:c.start_s)
        index = bisect_right([c.start_s for c in own], time_s)-1
        if index < 0 or time_s >= own[index].end_s:
            raise ValueError(f'{identity}: no hay ciclo físico en {time_s} s.')
        c = own[index]
        green_end, amber_end = c.start_s+c.green_s, c.start_s+c.green_s+c.yellow_s
        if time_s < green_end:
            phase, a, b = 'green', c.start_s, green_end
        elif time_s < amber_end:
            phase, a, b = 'yellow', green_end, amber_end
        else:
            phase, a, b = 'red', amber_end, c.end_s
        offset = c.start_s % c.duration_s
        states.append(dict(intersection_id=identity, time_s=time_s,
                           cycle_id=(c.start_s-offset)//c.duration_s+1,
                           phase=phase, phase_elapsed_s=time_s-a, phase_start_s=a, phase_end_s=b,
                           cycle_start_s=c.start_s, cycle_end_s=c.end_s,
                           green_start_s=c.start_s, green_end_s=green_end,
                           amber_start_s=green_end, amber_end_s=amber_end,
                           red_start_s=amber_end, red_end_s=c.end_s,
                           green_s=c.green_s, amber_s=c.yellow_s, red_s=c.red_s,
                           offset_s=offset, stage=c.stage))
    return states


def cycle_events(cycles, total_s, expected_cycle_s=None):
    """Emite G→A→R completo; solo recorta los extremos del horizonte visible.

    El siguiente ciclo empieza exactamente donde termina el anterior. Un
    cambio de plan no puede interrumpir un color ya iniciado.
    """
    total_s = whole_seconds(total_s, 'total_s')
    if expected_cycle_s is not None:
        expected_cycle_s = whole_seconds(expected_cycle_s, 'expected_cycle_s')
        if expected_cycle_s <= 0 or any(c.duration_s != expected_cycle_s for c in cycles):
            raise ValueError('La duración de cada ciclo físico debe ser el ciclo configurado.')
    result = []
    identities = dict.fromkeys(cycle.intersection_id for cycle in cycles)
    for identity in identities:
        own = sorted((c for c in cycles if c.intersection_id == identity), key=lambda c: c.start_s)
        if not own or own[0].start_s > 0 or own[-1].end_s < total_s:
            raise ValueError(f'{identity}: los ciclos no cubren el horizonte completo.')
        for previous, current in zip(own, own[1:]):
            if previous.end_s != current.start_s:
                raise ValueError(f'{identity}: salto o solapamiento entre ciclos en {current.start_s} s.')
        for cycle in own:
            start = cycle.start_s
            for state, duration in (('green', cycle.green_s), ('yellow', cycle.yellow_s), ('red', cycle.red_s)):
                end = start + duration
                a, b = max(0, start), min(total_s, end)
                if b > a:
                    result.append(dict(intersection_id=identity, state=state, start_s=a, end_s=b,
                                       duration_s=b - a, stages=cycle.stage,
                                       left_censored=int(a != start), right_censored=int(b != end)))
                start = end
    return result


def fixed_cycle_feasibility(current_offsets, target_offsets, cycle_s, allow_common_shift=True):
    """Una secuencia de períodos C conserva el offset de cada intersección.

    Un objetivo solo es alcanzable si ya coincide con los offsets actuales,
    permitiendo, cuando corresponde, una misma referencia común para todos.
    """
    cycle_s = whole_seconds(cycle_s, 'cycle_s')
    if cycle_s <= 0 or not current_offsets or len(current_offsets) != len(target_offsets):
        raise ValueError('Ciclo positivo y listas de offsets no vacías de igual longitud.')
    required = [(whole_seconds(old, 'current_offset') - whole_seconds(new, 'target_offset')) % cycle_s
                for old, new in zip(current_offsets, target_offsets)]
    shift = required[0] if allow_common_shift else 0
    return dict(feasible=all(value == shift for value in required),
                common_shift_s=shift,
                required_shifts_s=required,
                reason='Con inicios t[k+1] = t[k] + C, todos los offsets t[k] módulo C permanecen constantes.')
