from dataclasses import dataclass

from .errors import ConfigurationError


def require_integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise ConfigurationError(f"{name}: se requiere un entero")
    return value


@dataclass(frozen=True, slots=True)
class ControllerLimits:
    min_green_s: int = 0
    max_green_s: int = 99
    min_red_s: int = 0
    max_red_s: int = 99

    def __post_init__(self) -> None:
        for name in ("min_green_s", "max_green_s", "min_red_s", "max_red_s"):
            require_integer(getattr(self, name), name)
        if (self.min_green_s, self.max_green_s, self.min_red_s, self.max_red_s) != (0, 99, 0, 99):
            raise ConfigurationError("los límites del perfil conforme deben ser G/R=0..99")


@dataclass(frozen=True, slots=True)
class IntersectionConfig:
    id: str
    cycle_s: int
    yellow_s: int
    controller_profile_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ConfigurationError("id de intersección vacío")
        if not isinstance(self.controller_profile_id, str) or not self.controller_profile_id:
            raise ConfigurationError(f"{self.id}: falta controller_profile_id")
        require_integer(self.cycle_s, f"{self.id}.cycle_s")
        require_integer(self.yellow_s, f"{self.id}.yellow_s")
        if self.cycle_s <= 0 or not 0 <= self.yellow_s <= self.cycle_s:
            raise ConfigurationError(f"{self.id}: ciclo/amarillo fuera del dominio temporal")
        if not 0 <= self.cycle_s - self.yellow_s <= 198:
            raise ConfigurationError(f"{self.id}: ningún verde satisface G/R=0..99")

