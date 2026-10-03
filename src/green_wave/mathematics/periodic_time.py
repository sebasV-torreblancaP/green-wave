from green_wave.models.errors import ConfigurationError
from green_wave.models.intersection import require_integer
from green_wave.models.phase import BoundaryKind
from green_wave.models.timeline import PhaseBoundary, TemporalWindow


_BOUNDARIES = {
    ("R", "V"): BoundaryKind.RED_TO_GREEN,
    ("V", "A"): BoundaryKind.GREEN_TO_YELLOW,
    ("A", "R"): BoundaryKind.YELLOW_TO_RED,
}


def rotated_window(nominal: str, start_index_s: int, start_s: int) -> TemporalWindow:
    """Rotate one complete *known* period; start_index_s is supplied externally."""
    require_integer(start_index_s, "start_index_s")
    if not nominal or any(symbol not in "RVA" for symbol in nominal):
        raise ConfigurationError("periodo nominal inválido")
    index = start_index_s % len(nominal)
    return TemporalWindow(start_s, nominal[index:] + nominal[:index])


def observable_boundaries(window: TemporalWindow) -> tuple[PhaseBoundary, ...]:
    """Observable periodic changes, including the wrap at index zero.

    Missing phases have no observable boundary. Their fitness semantics remain open.
    """
    states = window.states
    result: list[PhaseBoundary] = []
    for index, after in enumerate(states):
        before = states[index - 1]
        if before == after:
            continue
        kind = _BOUNDARIES.get((before, after))
        if kind is not None:
            result.append(PhaseBoundary(kind, index))
    return tuple(result)

