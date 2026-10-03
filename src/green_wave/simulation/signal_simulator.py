from green_wave.mathematics.phenotype import nominal_period
from green_wave.models.errors import ConfigurationError
from green_wave.models.intersection import IntersectionConfig, require_integer
from green_wave.models.phase import Phase

from .trace import PhaseChange, PhaseSample, SignalTrace


def simulate_fixed_signal(intersection: IntersectionConfig, green_s: int, *,
                          green_origin_s: int, start_s: int, duration_s: int) -> SignalTrace:
    """Simulate a supplied, explicit green origin without planning a transition."""
    for name, value in (("green_origin_s", green_origin_s), ("start_s", start_s),
                        ("duration_s", duration_s)):
        require_integer(value, name)
    if duration_s <= 0:
        raise ConfigurationError("duration_s debe ser positivo")
    period = nominal_period(intersection, green_s)

    def phase_at(time_s: int) -> Phase:
        return Phase(period[(time_s - green_origin_s) % intersection.cycle_s])

    samples = tuple(PhaseSample(time_s, phase_at(time_s))
                    for time_s in range(start_s, start_s + duration_s))
    changes = tuple(PhaseChange(sample.time_s, phase_at(sample.time_s - 1), sample.phase)
                    for sample in samples if phase_at(sample.time_s - 1) != sample.phase)
    return SignalTrace(intersection.id, samples, changes)


def simulate_applied_steps(intersection: IntersectionConfig, initial_green_s: int, *,
                           green_origin_s: int, start_s: int, end_s: int,
                           applied_steps: tuple[tuple[int, int], ...]) -> SignalTrace:
    """Execute supplied changes at explicit cycle starts; no optimization here."""
    if end_s <= start_s:
        raise ConfigurationError("end_s debe ser mayor que start_s")
    for name, value in (("green_origin_s", green_origin_s), ("start_s", start_s), ("end_s", end_s)):
        require_integer(value, name)
    nominal_period(intersection, initial_green_s)
    last_time = start_s
    for time_s, green_s in applied_steps:
        require_integer(time_s, "applied_at_s")
        nominal_period(intersection, green_s)
        if time_s <= last_time or time_s >= end_s or (time_s - green_origin_s) % intersection.cycle_s:
            raise ConfigurationError("los cambios deben ser crecientes y ocurrir en inicios de ciclo internos")
        last_time = time_s

    samples: list[PhaseSample] = []
    changes: list[PhaseChange] = []
    current_green = initial_green_s
    next_step = iter(applied_steps)
    upcoming = next(next_step, None)
    previous = None
    for time_s in range(start_s, end_s):
        if upcoming is not None and time_s == upcoming[0]:
            current_green = upcoming[1]
            upcoming = next(next_step, None)
        period = nominal_period(intersection, current_green)
        phase = Phase(period[(time_s - green_origin_s) % intersection.cycle_s])
        samples.append(PhaseSample(time_s, phase))
        if previous is not None and previous != phase:
            changes.append(PhaseChange(time_s, previous, phase))
        previous = phase
    return SignalTrace(intersection.id, tuple(samples), tuple(changes))

