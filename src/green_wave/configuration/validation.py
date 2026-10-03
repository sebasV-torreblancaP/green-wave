from green_wave.mathematics.durations import red_duration
from green_wave.models.errors import ConfigurationError, InvalidCandidate
from green_wave.models.settings import Scenario


def validate_scenario(scenario: Scenario) -> None:
    ids = set(scenario.intersections)
    if set(scenario.plan_a.entries) != ids or set(scenario.plan_b.entries) != ids:
        raise ConfigurationError("Plan A y Plan B deben cubrir exactamente las intersecciones configuradas")
    for key, intersection in scenario.intersections.items():
        if intersection.id != key:
            raise ConfigurationError(f"clave {key} y id {intersection.id} no coinciden")
        if intersection.controller_profile_id not in scenario.controller_profiles:
            raise ConfigurationError(f"{key}: perfil de controlador inexistente")
        for plan in (scenario.plan_a, scenario.plan_b):
            try:
                red_duration(intersection, plan.entries[key].green_s)
            except InvalidCandidate as exc:
                raise ConfigurationError(f"{plan.name}: {exc}") from exc

