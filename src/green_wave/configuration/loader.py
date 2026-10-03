import json
from pathlib import Path

from green_wave.models.errors import ConfigurationError
from green_wave.models.intersection import ControllerLimits, IntersectionConfig
from green_wave.models.plan import PlanEntry, SignalPlan
from green_wave.models.settings import Scenario, TransitionSettings

from .schema import object_with_fields, path_list, string_field
from .validation import validate_scenario


def _json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"{path}: no se pudo leer JSON: {exc}") from exc


def _referenced(base: Path, raw: object, name: str) -> object:
    return _json(base / string_field(raw, name))


def _plan(raw: object, name: str) -> SignalPlan:
    data = object_with_fields(raw, name, {"name", "entries"})
    entries = data["entries"]
    if not isinstance(entries, dict) or not entries:
        raise ConfigurationError(f"{name}.entries: se requiere un objeto no vacío")
    parsed: dict[str, PlanEntry] = {}
    for key, entry in entries.items():
        string_field(key, f"{name}.id")
        item = object_with_fields(entry, f"{name}.{key}", {"green_s"})
        parsed[key] = PlanEntry(green_s=item["green_s"])
    return SignalPlan(name=string_field(data["name"], f"{name}.name"), entries=parsed)


def load_scenario(path: str | Path) -> Scenario:
    source = Path(path)
    data = object_with_fields(_json(source), str(source), {
        "schema_version", "id", "h_inicio_s", "intersection_files", "controller_profiles_file",
        "plan_a_file", "plan_b_file", "transition_file",
    })
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigurationError("schema_version debe ser 1")
    base = source.parent
    intersections: dict[str, IntersectionConfig] = {}
    for filename in path_list(data["intersection_files"], "intersection_files"):
        item = object_with_fields(_json(base / filename), filename, {
            "id", "cycle_s", "yellow_s", "controller_profile_id",
        })
        intersection = IntersectionConfig(**item)
        if intersection.id in intersections:
            raise ConfigurationError(f"intersección duplicada: {intersection.id}")
        intersections[intersection.id] = intersection
    profiles_data = _referenced(base, data["controller_profiles_file"], "controller_profiles_file")
    if not isinstance(profiles_data, dict) or not profiles_data:
        raise ConfigurationError("controller_profiles_file: se requiere un objeto no vacío")
    profiles = {
        string_field(name, "controller_profile_id"): ControllerLimits(**object_with_fields(profile, name, {
            "min_green_s", "max_green_s", "min_red_s", "max_red_s",
        })) for name, profile in profiles_data.items()
    }
    transition_data = object_with_fields(_referenced(base, data["transition_file"], "transition_file"),
        "transition", {"candidates_per_intersection", "max_green_change_percent", "max_generations",
                       "stagnation_generations", "elite_count", "state_weight", "boundary_weight",
                       "target_fitness", "max_transition_cycles"})
    scenario = Scenario(
        id=string_field(data["id"], "id"),
        h_inicio_s=data["h_inicio_s"],
        intersections=intersections,
        controller_profiles=profiles,
        plan_a=_plan(_referenced(base, data["plan_a_file"], "plan_a_file"), "plan_a"),
        plan_b=_plan(_referenced(base, data["plan_b_file"], "plan_b_file"), "plan_b"),
        transition=TransitionSettings(**transition_data),
    )
    validate_scenario(scenario)
    return scenario


def load_reference_policy(path: str | Path, scenario: Scenario, metric: str):
    """Load explicit origins for the provisional reference execution."""
    from green_wave.algorithms.transition_policy import ReferencePolicy

    data = object_with_fields(_json(Path(path)), str(path), {"A", "B"})
    for name in ("A", "B"):
        if not isinstance(data[name], dict):
            raise ConfigurationError(f"orígenes de {name}: se requiere un objeto")
    policy = ReferencePolicy(data["A"], data["B"], metric,
                             "next_green_start", "per_intersection")
    policy.validate(scenario)
    return policy


def load_genetic_choices(path: str | Path):
    from green_wave.optimization.genetic.optimizer import GeneticChoices

    data = object_with_fields(_json(Path(path)), str(path), {
        "parent_strategy", "mutation_probability", "mutation_amplitude_s",
        "current_in_every_generation", "seed",
    })
    return GeneticChoices(**data)
