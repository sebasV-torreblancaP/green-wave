from collections.abc import Mapping

from green_wave.models.errors import ConfigurationError


def object_with_fields(value: object, name: str, fields: set[str]) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name}: se requiere un objeto JSON")
    missing = fields - value.keys()
    extra = value.keys() - fields
    if missing or extra:
        raise ConfigurationError(f"{name}: faltan {sorted(missing)}, sobran {sorted(extra)}")
    return value


def string_field(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{name}: se requiere texto no vacío")
    return value


def path_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ConfigurationError(f"{name}: se requiere una lista no vacía")
    return [string_field(item, f"{name}[{i}]") for i, item in enumerate(value)]

