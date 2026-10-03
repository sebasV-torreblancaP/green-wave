from heapq import heappop, heappush
from dataclasses import asdict

from green_wave.evaluation.boundary_fitness import boundary_fitness
from green_wave.evaluation.evaluator import evaluate
from green_wave.mathematics.periodic_time import rotated_window
from green_wave.mathematics.phenotype import nominal_period
from green_wave.mathematics.feasible_domain import next_green_domain, physical_domain
from green_wave.models.errors import ConfigurationError, ModelDecisionRequired
from green_wave.models.intersection import IntersectionConfig
from green_wave.models.settings import Scenario
from green_wave.models.timeline import TemporalWindow
from green_wave.models.transition import TransitionResult, TransitionStatus, TransitionStep
from green_wave.optimization.exhaustive import ExhaustiveOptimizer
from green_wave.optimization.genetic.optimizer import GeneticChoices, GeneticOptimizer
from green_wave.optimization.interfaces import Optimizer
from green_wave.optimization.search_context import SearchContext
from green_wave.simulation.signal_simulator import simulate_applied_steps

from .termination import all_aligned
from .transition_policy import ReferencePolicy, next_green_start_strictly_after


def _window(intersection: IntersectionConfig, green_s: int, origin_s: int,
            start_s: int) -> TemporalWindow:
    period = nominal_period(intersection, green_s)
    return rotated_window(period, start_s - origin_s, start_s)


def _fitness(intersection: IntersectionConfig, green_s: int, origin_s: int,
             target_green_s: int, target_origin_s: int, start_s: int, metric: str) -> float:
    candidate = _window(intersection, green_s, origin_s, start_s)
    target = _window(intersection, target_green_s, target_origin_s, start_s)
    return evaluate(candidate, target, lambda left, right: boundary_fitness(left, right, metric)).total


def _unreachable_reason(intersection: IntersectionConfig, start_green_s: int,
                        target_green_s: int, origin_a_s: int, origin_b_s: int,
                        start_s: int) -> str | None:
    target_states = _window(intersection, target_green_s, origin_b_s, start_s).states
    desired = {green for green in physical_domain(intersection).values()
               if _window(intersection, green, origin_a_s, start_s).states == target_states}
    if not desired:
        return "Plan B no es representable con G y el origen de verde A fijado"
    reached = {start_green_s}
    frontier = [start_green_s]
    while frontier:
        current = frontier.pop()
        if current in desired:
            return None
        for neighbor in next_green_domain(intersection, current).values():
            if neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return "no existe una trayectoria de verdes enteros con pasos de ±20 % hasta Plan B"


def run_reference(scenario: Scenario, policy: ReferencePolicy) -> TransitionResult:
    """Run a provisional transition using a deterministic reference search."""
    return _run(scenario, policy, ExhaustiveOptimizer(), "exhaustive", {})


def run_genetic(scenario: Scenario, policy: ReferencePolicy,
                choices: GeneticChoices) -> TransitionResult:
    """Run the one-gene GA under caller-selected, provisional operators."""
    settings = scenario.transition
    optimizer = GeneticOptimizer(choices, population_size=settings.candidates_per_intersection,
                                 elite_count=settings.elite_count,
                                 max_generations=settings.max_generations,
                                 stagnation_generations=settings.stagnation_generations)
    return _run(scenario, policy, optimizer, "genetic", asdict(choices))


def _run(scenario: Scenario, policy: ReferencePolicy, optimizer: Optimizer,
         method: str, optimizer_parameters: dict[str, object]) -> TransitionResult:
    policy.validate(scenario)
    for key, intersection in scenario.intersections.items():
        for plan in (scenario.plan_a, scenario.plan_b):
            green = plan.entries[key].green_s
            red = intersection.cycle_s - intersection.yellow_s - green
            if min(green, red, intersection.yellow_s) == 0:
                raise ModelDecisionRequired(f"{key}: D06 exige política para fases de duración cero")

    greens = {key: scenario.plan_a.entries[key].green_s for key in scenario.intersections}
    fitness = {
        key: _fitness(intersection, greens[key], policy.plan_a_green_origins_s[key],
                      scenario.plan_b.entries[key].green_s, policy.plan_b_green_origins_s[key],
                      scenario.h_inicio_s, policy.boundary_metric)
        for key, intersection in scenario.intersections.items()
    }
    diagnostics = {
        key: reason for key, intersection in scenario.intersections.items()
        if (reason := _unreachable_reason(intersection, greens[key],
                scenario.plan_b.entries[key].green_s, policy.plan_a_green_origins_s[key],
                policy.plan_b_green_origins_s[key], scenario.h_inicio_s)) is not None
    }
    if diagnostics:
        trace_end = scenario.h_inicio_s + max(item.cycle_s for item in scenario.intersections.values())
        traces = {
            key: simulate_applied_steps(intersection, greens[key],
                                        green_origin_s=policy.plan_a_green_origins_s[key],
                                        start_s=scenario.h_inicio_s, end_s=trace_end, applied_steps=())
            for key, intersection in scenario.intersections.items()
        }
        return TransitionResult(TransitionStatus.UNREACHABLE, scenario.h_inicio_s,
                                scenario.h_inicio_s, (), greens, fitness, traces, method,
                                policy.application, policy.boundary_metric, optimizer_parameters, diagnostics)
    events: list[tuple[int, str]] = []
    for key, intersection in scenario.intersections.items():
        if fitness[key] != 1.0:
            heappush(events, (next_green_start_strictly_after(
                scenario.h_inicio_s, policy.plan_a_green_origins_s[key], intersection.cycle_s), key))
    history: list[TransitionStep] = []
    counts = {key: 0 for key in scenario.intersections}
    status = TransitionStatus.COMPLETED
    ended_at_s = scenario.h_inicio_s

    while events:
        time_s, key = heappop(events)
        intersection = scenario.intersections[key]
        current_green = greens[key]
        origin_a = policy.plan_a_green_origins_s[key]
        target_green = scenario.plan_b.entries[key].green_s
        origin_b = policy.plan_b_green_origins_s[key]

        def score(proposed_green: int) -> float:
            return _fitness(intersection, proposed_green, origin_a,
                            target_green, origin_b, time_s, policy.boundary_metric)

        previous_fitness = score(current_green)
        outcome = optimizer.search(SearchContext(intersection, current_green), score)
        if outcome.best_score < previous_fitness:
            raise ConfigurationError(f"{key}: el optimizador produjo una regresión")
        counts[key] += 1
        history.append(TransitionStep(key, counts[key], time_s, current_green, outcome.best_green_s,
                                      previous_fitness, outcome.best_score, outcome.generations,
                                      outcome.evaluated, outcome.reason))
        greens[key] = outcome.best_green_s
        fitness[key] = outcome.best_score
        ended_at_s = max(ended_at_s, time_s)
        if outcome.best_score == 1.0:
            continue
        if counts[key] >= scenario.transition.max_transition_cycles:
            status = TransitionStatus.INCOMPLETE_LIMIT
            break
        heappush(events, (time_s + intersection.cycle_s, key))

    if status is TransitionStatus.COMPLETED and not all_aligned(fitness):
        raise ConfigurationError("la cola terminó con intersecciones todavía activas")
    trace_end = ended_at_s + max(item.cycle_s for item in scenario.intersections.values())
    traces = {
        key: simulate_applied_steps(intersection, scenario.plan_a.entries[key].green_s,
                                    green_origin_s=policy.plan_a_green_origins_s[key],
                                    start_s=scenario.h_inicio_s, end_s=trace_end,
                                    applied_steps=tuple((step.applied_at_s, step.next_green_s)
                                                        for step in history if step.intersection_id == key))
        for key, intersection in scenario.intersections.items()
    }
    return TransitionResult(status, scenario.h_inicio_s, ended_at_s, tuple(history), greens,
                            fitness, traces, method, policy.application, policy.boundary_metric,
                            optimizer_parameters)
