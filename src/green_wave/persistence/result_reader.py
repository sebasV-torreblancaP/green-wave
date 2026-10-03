import json
from pathlib import Path

from green_wave.models.errors import ConfigurationError
from green_wave.models.phase import Phase
from green_wave.simulation.trace import PhaseChange, PhaseSample, SignalTrace

from green_wave.configuration.schema import object_with_fields, string_field


def read_trace(source: str | Path) -> SignalTrace:
    path = Path(source)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        data = object_with_fields(raw, str(path), {"schema_version", "intersection_id", "samples", "changes"})
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ConfigurationError("versión de traza no soportada")
        if not isinstance(data["samples"], list) or not isinstance(data["changes"], list):
            raise ConfigurationError("listas de traza inválidas")
        samples = tuple(PhaseSample(item["time_s"], Phase(item["phase"]))
                        for item in data["samples"])
        changes = tuple(PhaseChange(item["time_s"], Phase(item["previous"]), Phase(item["next"]))
                        for item in data["changes"])
        trace = SignalTrace(string_field(data["intersection_id"], "intersection_id"), samples, changes)
        if any(current.time_s != previous.time_s + 1 for previous, current in zip(samples, samples[1:])):
            raise ConfigurationError("muestras de traza no consecutivas")
        return trace
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"{path}: traza inválida: {exc}") from exc
