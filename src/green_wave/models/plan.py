from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .errors import ConfigurationError
from .intersection import require_integer


@dataclass(frozen=True, slots=True)
class PlanEntry:
    green_s: int

    def __post_init__(self) -> None:
        require_integer(self.green_s, "green_s")


@dataclass(frozen=True, slots=True)
class SignalPlan:
    name: str
    entries: Mapping[str, PlanEntry]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ConfigurationError("nombre de plan vacío")
        if not isinstance(self.entries, Mapping) or not self.entries:
            raise ConfigurationError(f"{self.name}: plan sin intersecciones")
        if not all(isinstance(k, str) and k and isinstance(v, PlanEntry) for k, v in self.entries.items()):
            raise ConfigurationError(f"{self.name}: entradas de plan inválidas")
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))

