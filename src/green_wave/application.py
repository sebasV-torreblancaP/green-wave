from pathlib import Path

from green_wave.algorithms.transition_engine import run_reference
from green_wave.configuration.loader import load_reference_policy, load_scenario
from green_wave.models.transition import TransitionResult


def run_reference_from_files(scenario_file: str | Path, origins_file: str | Path,
                             boundary_metric: str) -> TransitionResult:
    scenario = load_scenario(scenario_file)
    policy = load_reference_policy(origins_file, scenario, boundary_metric)
    return run_reference(scenario, policy)
