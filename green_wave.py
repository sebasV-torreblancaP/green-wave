from dataclasses import dataclass, field
from typing import List
import math
from decimal import Decimal, ROUND_FLOOR
from fractions import Fraction


@dataclass
class Intersection:
    id: str
    distance_m: float


@dataclass
class WavePlan:
    direction: str
    speed_kmh: float
    offsets_s: List[int]

    def parameters(self, intersections):
        source = intersections[0] if self.direction == 'up' else intersections[-1]
        return dict(direction=self.direction, speed_kmh=self.speed_kmh,
                    offsets_s=self.offsets_s.copy(),
                    travel_times_s=[travel_time_s(abs(x.distance_m-source.distance_m), self.speed_kmh)
                                    for x in intersections])


@dataclass(frozen=True)
class PhaseDurationAdjustment:
    """Cambio de reparto; nunca es un desplazamiento del inicio del ciclo."""
    green_delta_s: int
    red_delta_s: int

    def __post_init__(self):
        object.__setattr__(self,'green_delta_s',whole_seconds(self.green_delta_s,'green_delta_s'))
        object.__setattr__(self,'red_delta_s',whole_seconds(self.red_delta_s,'red_delta_s'))
        if self.green_delta_s + self.red_delta_s != 0:
            raise ValueError('Cada cambio de verde requiere la compensación opuesta en rojo.')


@dataclass(frozen=True)
class PhaseOffsetCorrection:
    """Corrección solicitada y corrección física realmente aplicada."""
    requested_s: int
    applied_s: int
    achievable: bool
    reason: str


def assess_phase_offset(current_offset, target_offset, cycle_s):
    """Un período físico fijo obliga a que el desplazamiento aplicado sea cero."""
    cycle_s = whole_seconds(cycle_s, 'cycle_s')
    if cycle_s <= 0:
        raise ValueError('El ciclo debe ser positivo.')
    current_offset = whole_seconds(current_offset, 'current_offset') % cycle_s
    target_offset = whole_seconds(target_offset, 'target_offset') % cycle_s
    difference = (target_offset-current_offset) % cycle_s
    if difference > cycle_s//2:
        difference -= cycle_s
    return PhaseOffsetCorrection(difference, 0, difference == 0,
        'TARGET ACHIEVABLE' if difference == 0 else
        'TARGET NOT ACHIEVABLE UNDER CURRENT CONSTRAINTS: '
        't[k+1]=t[k]+C conserva el inicio de verde módulo C; ΔG=-ΔR no mueve ese inicio.')


def choose_nominal_green(current_green, nominal_green, cycle_s, yellow_s,
                          fraction, min_green_s=1, max_green_s=None,
                          min_red_s=1, green_step_s=None):
    """Reevalúa todas las órdenes enteras permitidas en el ciclo actual.

    Primero minimiza el error nominal; entre opciones equivalentes minimiza
    el cambio. El movimiento hacia el objetivo tiene el menor número posible
    de ciclos bajo las restricciones de paso y desviación nominal.
    """
    current_green = whole_seconds(current_green, 'current_green')
    nominal_green = whole_seconds(nominal_green, 'nominal_green')
    cycle_s = whole_seconds(cycle_s, 'cycle_s')
    yellow_s = whole_seconds(yellow_s, 'yellow_s')
    min_green_s = whole_seconds(min_green_s, 'min_green_s')
    min_red_s = whole_seconds(min_red_s, 'min_red_s')
    cap = cycle_s-yellow_s-min_red_s
    max_green_s = cap if max_green_s is None else whole_seconds(max_green_s, 'max_green_s')
    if not math.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError('La fracción debe estar entre 0 y 1.')
    if cycle_s <= 0 or yellow_s < 0 or min_green_s <= 0 or min_red_s <= 0:
        raise ValueError('Ciclo y mínimos positivos; amarillo no negativo.')
    limit = int((Decimal(nominal_green)*Decimal(str(fraction))).to_integral_value(rounding=ROUND_FLOOR))
    step = limit if green_step_s is None else min(limit, whole_seconds(green_step_s, 'green_step_s'))
    if step < 0 or green_step_s is not None and green_step_s <= 0:
        raise ValueError('green_step_s debe ser positivo.')
    lower = max(min_green_s, nominal_green-limit)
    upper = min(max_green_s, cap, nominal_green+limit)
    if not lower <= current_green <= upper or not lower <= nominal_green <= upper:
        raise ValueError('El reparto actual o nominal viola los límites físicos o porcentuales.')
    if current_green != nominal_green and step == 0:
        raise ValueError('La capacidad entera no permite restaurar el verde nominal.')
    candidates = range(max(lower, current_green-step), min(upper, current_green+step)+1)
    selected = min(candidates, key=lambda g: (abs(g-nominal_green), abs(g-current_green), g))
    delta = selected-current_green
    return selected, PhaseDurationAdjustment(delta, -delta)


@dataclass
class TransitionResult:
    green_history: List[List[int]]
    offset_history: List[List[int]]
    cycles_used: int
    final_offsets_s: List[int]
    red_history: List[List[int]]
    target_offsets_s: List[int]
    target_phase_shift_s: int
    cycle_s: int
    yellow_s: int
    final_green_s: List[int] = field(default_factory=list)


def travel_time_s(distance_m: float, speed_kmh: float) -> float:
    if not math.isfinite(speed_kmh) or speed_kmh <= 0:
        raise ValueError('La velocidad debe ser finita y mayor que cero.')
    return distance_m / (speed_kmh * 1000.0 / 3600.0)


def normalize_offset(value_s: float, cycle_s: float) -> float:
    return value_s % cycle_s


def whole_seconds(value, name):
    """Valida tiempos configurados sin redondearlos silenciosamente."""
    if isinstance(value, bool) or not math.isfinite(float(value)) or not float(value).is_integer():
        raise ValueError(f'{name} debe expresarse en segundos enteros: {value}.')
    return int(value)


def calculate_wave_plan(intersections, cycle_s, speed_kmh, direction, reference_offset_s=0):
    """Offsets ideales, al segundo más cercano (mitades hacia arriba)."""
    cycle_s = whole_seconds(cycle_s, 'cycle_s')
    reference_offset_s = whole_seconds(reference_offset_s, 'reference_offset_s')
    if cycle_s <= 0:
        raise ValueError('El ciclo debe ser positivo.')
    if direction == 'up':
        distances = [x.distance_m for x in intersections]
    elif direction == 'down':
        distances = [intersections[-1].distance_m - x.distance_m for x in intersections]
    else:
        raise ValueError("direction debe ser 'up' o 'down'.")
    offsets = [math.floor(reference_offset_s + travel_time_s(d, speed_kmh) + 0.5) % cycle_s
               for d in distances]
    return WavePlan(direction, speed_kmh, offsets)


def circular_difference(target_s, current_s, cycle_s):
    return (target_s - current_s + cycle_s / 2.0) % cycle_s - cycle_s / 2.0


def phase_error(target_offsets_s, actual_offsets_s, cycle_s):
    return [circular_difference(t, a, cycle_s) for t, a in zip(target_offsets_s, actual_offsets_s)]


def transition_to_target_offsets(current_offsets_s, target_offsets_s, base_green_s,
                                 cycle_s, max_change_fraction=0.20, max_cycles=20,
                                 yellow_s=4, optimize_target_phase=False,
                                 min_green_s=1, min_red_s=1, target_green_s=None,
                                 green_step_s=1):
    """Ciclos físicos de C segundos: solo cambia G; R = C - G - A.

    Los inicios permanecen anclados. Rechaza offsets incompatibles en lugar
    de desplazar fases en una rejilla y cortar colores ya iniciados.
    El porcentaje limita tanto el reparto respecto a la base como el cambio
    entre ciclos; green_step_s permite una rampa más lenta.
    """
    cycle_s = whole_seconds(cycle_s, 'cycle_s')
    yellow_s = whole_seconds(yellow_s, 'yellow_s')
    min_green_s = whole_seconds(min_green_s, 'min_green_s')
    min_red_s = whole_seconds(min_red_s, 'min_red_s')
    green_step_s = whole_seconds(green_step_s, 'green_step_s')
    if cycle_s <= 0 or yellow_s < 0 or min_green_s <= 0 or min_red_s <= 0 or green_step_s <= 0:
        raise ValueError('Ciclo, mínimos y paso positivos; amarillo no negativo.')
    if not math.isfinite(max_change_fraction) or not 0 < max_change_fraction < 1:
        raise ValueError('La fracción debe estar entre 0 y 1.')
    if isinstance(max_cycles, bool) or not isinstance(max_cycles, int) or max_cycles < 1:
        raise ValueError('max_cycles debe ser un entero positivo.')
    if not base_green_s or not len(current_offsets_s) == len(target_offsets_s) == len(base_green_s):
        raise ValueError('Los offsets y verdes deben tener la misma longitud no vacía.')
    base = [whole_seconds(g, 'base_green_s') for g in base_green_s]
    current = [whole_seconds(x, 'current_offsets_s') % cycle_s for x in current_offsets_s]
    target = [whole_seconds(x, 'target_offsets_s') % cycle_s for x in target_offsets_s]
    final = base.copy() if target_green_s is None else [whole_seconds(g, 'target_green_s') for g in target_green_s]
    if len(final) != len(base):
        raise ValueError('target_green_s debe tener un valor por semáforo.')
    limits = [int((Decimal(g) * Decimal(str(max_change_fraction))).to_integral_value(rounding=ROUND_FLOOR))
              for g in base]
    for g, f, limit in zip(base, final, limits):
        if min(g, f) < min_green_s or cycle_s - max(g, f) - yellow_s < min_red_s:
            raise ValueError('El verde y el rojo deben respetar sus mínimos.')
        if abs(f - g) > limit:
            raise ValueError('El verde objetivo excede el límite respecto al verde base.')
    shifts = [(a - b) % cycle_s for a, b in zip(current, target)]
    shift = shifts[0] if optimize_target_phase else 0
    if any(s != shift for s in shifts):
        raise ValueError('Offsets inalcanzables con ciclo físico fijo: no se pueden mover los inicios de verde.')
    steps = [min(green_step_s, limit) for limit in limits]
    if any(a != b and step == 0 for a, b, step in zip(base, final, steps)):
        raise ValueError('El límite entero no permite modificar el verde.')
    count = max(((abs(b-a) + step-1)//step if a != b else 0)
                for a, b, step in zip(base, final, steps))
    if count > max_cycles:
        raise ValueError(f'La rampa necesita {count} ciclos; aumenta max_transition_cycles a {count} o más.')
    greens = [[a + (1 if b >= a else -1) * min(abs(b-a), (k+1)*step)
               for a, b, step in zip(base, final, steps)] for k in range(count)]
    return TransitionResult(greens, [current.copy() for _ in range(count+1)], count,
                            current.copy(), [[cycle_s-yellow_s-g for g in row] for row in greens],
                            current.copy(), int(circular_difference(shift, 0, cycle_s)),
                            cycle_s, yellow_s, final)


def _departure_windows_exact(intersections, plan, greens, cycle):
    """Ventanas con aritmética racional, incluyendo una banda que cruza cero."""
    cycle = Fraction(cycle)
    source = intersections[0] if plan.direction == 'up' else intersections[-1]
    windows = [(Fraction(0), cycle)]
    for inter, offset, green in zip(intersections, plan.offsets_s, greens):
        travel = abs(Fraction(str(inter.distance_m))-Fraction(str(source.distance_m))) * Fraction(18, 5) / Fraction(str(plan.speed_kmh))
        start = (offset - travel) % cycle
        end = start + green
        allowed = [(start, min(end, cycle))]
        if end > cycle:
            allowed.append((Fraction(0), end-cycle))
        windows = [(max(a, c), min(b, d)) for a, b in windows for c, d in allowed
                   if max(a, c) < min(b, d)]
    windows.sort()
    if len(windows) > 1 and windows[0][0] == 0 and windows[-1][1] == cycle:
        # No pierde bandas continuas que atraviesan el origen de la referencia.
        windows = windows[1:-1] + [(windows[-1][0], cycle+windows[0][1])]
    return windows


def find_down_green_target(intersections, offsets, base_greens, cycle, yellow,
                            speed_kmh, min_red_s=1, min_band_s=1):
    """Mínima relajación uniforme respecto a la base para una banda BAJADA.

    Enumera TODOS los umbrales de capacidad enteros: (G-base)/base.
    La primera capacidad con banda suficiente demuestra el mínimo global;
    no depende de muestrear velocidades ni instantes de salida.
    """
    cycle = whole_seconds(cycle, 'cycle_s')
    yellow = whole_seconds(yellow, 'yellow_s')
    min_red_s = whole_seconds(min_red_s, 'min_red_s')
    offsets = [whole_seconds(o, 'offset_s') for o in offsets]
    base_greens = [whole_seconds(g, 'base_green_s') for g in base_greens]
    if not intersections or not len(intersections) == len(offsets) == len(base_greens):
        raise ValueError('Intersecciones, offsets y verdes deben tener la misma longitud no vacía.')
    if cycle <= 0 or yellow < 0 or min_red_s <= 0 or any(g <= 0 or g+yellow+min_red_s > cycle for g in base_greens):
        raise ValueError('El reparto base debe respetar el ciclo y los mínimos físicos.')
    min_band_s = whole_seconds(min_band_s, 'min_down_band_s')
    if min_band_s <= 0:
        raise ValueError('min_down_band_s debe ser positivo.')
    travel_time_s(0, speed_kmh)
    cap = cycle-yellow-min_red_s
    plan = WavePlan('down', speed_kmh, offsets)
    candidates = sorted({Fraction(g-base, base) for base in base_greens for g in range(base, cap+1)})
    for fraction in candidates:
        capacity = [min(cap, g + int(g*fraction)) for g in base_greens]
        windows = [(a, b) for a, b in _departure_windows_exact(intersections, plan, capacity, cycle)
                   if b-a >= min_band_s]
        if not windows:
            continue
        departure, _ = min(windows)
        source = Fraction(str(intersections[-1].distance_m))
        target = []
        for inter, offset, base in zip(intersections, offsets, base_greens):
            travel = (source-Fraction(str(inter.distance_m))) * Fraction(18, 5) / Fraction(str(speed_kmh))
            phase = (departure+travel-offset) % cycle
            target.append(max(base, math.ceil(phase+min_band_s)))
        exact_fraction = max(Fraction(g-base, base) for g, base in zip(target, base_greens))
        # Redondear hacia arriba para que Decimal(base * fracción) conserve la capacidad.
        suggested = math.ceil(exact_fraction*1_000_000)/1_000_000
        return dict(target_green_s=target, minimum_fraction=str(exact_fraction),
                    suggested_fraction=suggested, departure_s=float(departure),
                    departure_exact_s=str(departure),
                    windows_s=[(float(a), float(b)) for a, b in
                               _departure_windows_exact(intersections, plan, target, cycle)],
                    min_band_s=min_band_s)
    raise ValueError('No existe banda BAJADA con los mínimos físicos de rojo y amarillo.')
