from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .errors import ConfigurationError
from .intersection import ControllerLimits, IntersectionConfig, require_integer
from .plan import SignalPlan


@dataclass(frozen=True, slots=True)
class TransitionSettings:
    candidates_per_intersection: int
    max_green_change_percent: int
    max_generations: int
    stagnation_generations: int
    elite_count: int
    state_weight: float
    boundary_weight: float
    target_fitness: float
    max_transition_cycles: int

    def __post_init__(self) -> None:
        for name in ("candidates_per_intersection", "max_green_change_percent", "max_generations",
                     "stagnation_generations", "elite_count", "max_transition_cycles"):
            require_integer(getattr(self, name), name)
        if self.candidates_per_intersection != 15 or self.max_green_change_percent != 20:
            raise ConfigurationError("el perfil conforme exige 15 candidatos y cambio máximo del 20 %")
        if self.max_generations != 100 or self.stagnation_generations != 10 or self.elite_count != 5:
            raise ConfigurationError("el perfil conforme exige 100 generaciones, estancamiento 10 y 5 élites")
        if self.state_weight != 0.5 or self.boundary_weight != 0.5 or self.target_fitness != 1.0:
            raise ConfigurationError("el perfil conforme exige pesos 0.5/0.5 y objetivo 1.0")
        if self.max_transition_cycles <= 0:
            raise ConfigurationError("max_transition_cycles debe ser positivo")


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    h_inicio_s: int
    intersections: Mapping[str, IntersectionConfig]
    controller_profiles: Mapping[str, ControllerLimits]
    plan_a: SignalPlan
    plan_b: SignalPlan
    transition: TransitionSettings

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ConfigurationError("id de escenario vacío")
        require_integer(self.h_inicio_s, "h_inicio_s")
        if not self.intersections:
            raise ConfigurationError("el escenario no contiene intersecciones")
        object.__setattr__(self, "intersections", MappingProxyType(dict(self.intersections)))
        object.__setattr__(self, "controller_profiles", MappingProxyType(dict(self.controller_profiles)))

