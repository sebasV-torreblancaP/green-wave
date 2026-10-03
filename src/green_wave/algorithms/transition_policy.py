from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from green_wave.evaluation.boundary_fitness import BoundaryMetric
from green_wave.models.errors import ConfigurationError
from green_wave.models.intersection import require_integer
from green_wave.models.settings import Scenario


@dataclass(frozen=True, slots=True)
class ReferencePolicy:
    """Explicit, provisional semantics for the reference implementation."""

    plan_a_green_origins_s: Mapping[str, int]
    plan_b_green_origins_s: Mapping[str, int]
    boundary_metric: BoundaryMetric
    application: str
    cycle_limit_scope: str

    def __post_init__(self) -> None:
        if self.boundary_metric not in ("circular", "linear"):
            raise ConfigurationError("métrica de fronteras desconocida")
        if self.application != "next_green_start" or self.cycle_limit_scope != "per_intersection":
            raise ConfigurationError("solo se implementó la política explícita next_green_start/per_intersection")
        for name in ("plan_a_green_origins_s", "plan_b_green_origins_s"):
            origins = dict(getattr(self, name))
            for key, value in origins.items():
                require_integer(value, f"{name}.{key}")
            object.__setattr__(self, name, MappingProxyType(origins))

    def validate(self, scenario: Scenario) -> None:
        ids = set(scenario.intersections)
        if set(self.plan_a_green_origins_s) != ids or set(self.plan_b_green_origins_s) != ids:
            raise ConfigurationError("los orígenes de A y B deben cubrir exactamente las intersecciones")


def next_green_start_strictly_after(time_s: int, origin_s: int, cycle_s: int) -> int:
    return time_s + cycle_s - ((time_s - origin_s) % cycle_s)

