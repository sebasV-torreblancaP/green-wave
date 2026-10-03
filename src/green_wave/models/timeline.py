from dataclasses import dataclass

from .errors import ConfigurationError
from .intersection import require_integer
from .phase import BoundaryKind, Phase


@dataclass(frozen=True, slots=True)
class TemporalWindow:
    start_s: int
    states: str

    def __post_init__(self) -> None:
        require_integer(self.start_s, "start_s")
        if not self.states or any(symbol not in Phase._value2member_map_ for symbol in self.states):
            raise ConfigurationError("ventana temporal vacía o con colores desconocidos")

    @property
    def duration_s(self) -> int:
        return len(self.states)


@dataclass(frozen=True, slots=True)
class PhaseBoundary:
    kind: BoundaryKind
    position_s: int

