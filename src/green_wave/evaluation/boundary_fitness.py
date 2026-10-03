from typing import Literal

from green_wave.models.errors import ConfigurationError, ModelDecisionRequired
from green_wave.models.timeline import TemporalWindow
from green_wave.mathematics.periodic_time import observable_boundaries


BoundaryMetric = Literal["circular", "linear"]


def boundary_fitness(candidate: TemporalWindow, target: TemporalWindow,
                     metric: BoundaryMetric | None = None) -> float:
    """Score three observable borders under an explicitly selected metric.

    The model has not selected a metric or defined missing-border behavior.
    """
    if metric is None:
        raise ModelDecisionRequired("D06: seleccionar métrica y resolver fases de duración cero")
    if metric not in ("circular", "linear"):
        raise ConfigurationError(f"métrica de fronteras desconocida: {metric}")
    if candidate.start_s != target.start_s or candidate.duration_s != target.duration_s:
        raise ConfigurationError("las ventanas de frontera deben compartir origen y duración")
    cycle = candidate.duration_s
    source = observable_boundaries(candidate)
    goal = observable_boundaries(target)
    if cycle < 3 or len(source) != 3 or len(goal) != 3:
        raise ModelDecisionRequired("D06: faltan fronteras observables o el ciclo es demasiado corto")
    source_positions = {item.kind: item.position_s for item in source}
    goal_positions = {item.kind: item.position_s for item in goal}
    if source_positions.keys() != goal_positions.keys() or len(source_positions) != 3:
        raise ModelDecisionRequired("D06: las tres fronteras no son comparables")
    differences = [abs(source_positions[kind] - goal_positions[kind]) for kind in goal_positions]
    if metric == "circular":
        distance = sum(min(value, cycle - value) for value in differences)
        maximum = 3 * (cycle // 2)
    else:
        distance = sum(differences)
        maximum = 3 * (cycle - 1)
    return 1 - distance / maximum
