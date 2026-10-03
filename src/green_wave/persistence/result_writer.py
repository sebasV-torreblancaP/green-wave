import json
import csv
from pathlib import Path

from green_wave.simulation.trace import SignalTrace


def trace_data(trace: SignalTrace) -> dict[str, object]:
    return {
        "schema_version": 1,
        "intersection_id": trace.intersection_id,
        "samples": [{"time_s": item.time_s, "phase": item.phase.value} for item in trace.samples],
        "changes": [{"time_s": item.time_s, "previous": item.previous.value,
                     "next": item.next.value} for item in trace.changes],
    }


def write_trace(trace: SignalTrace, destination: str | Path) -> None:
    path = Path(destination)
    path.write_text(json.dumps(trace_data(trace), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def result_data(result) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": result.status.value,
        "started_at_s": result.started_at_s,
        "ended_at_s": result.ended_at_s,
        "method": result.method,
        "application_policy": result.policy,
        "cycle_limit_scope": "per_intersection",
        "boundary_metric": result.boundary_metric,
        "optimizer_parameters": dict(result.optimizer_parameters),
        "diagnostics": dict(result.diagnostics),
        "steps": [{"intersection_id": step.intersection_id, "local_cycle": step.local_cycle,
                   "applied_at_s": step.applied_at_s, "previous_green_s": step.previous_green_s,
                   "next_green_s": step.next_green_s, "previous_fitness": step.previous_fitness,
                   "next_fitness": step.next_fitness, "optimizer_generations": step.optimizer_generations,
                   "evaluated_candidates": step.evaluated_candidates,
                   "optimizer_reason": step.optimizer_reason} for step in result.steps],
        "final_green_s": dict(result.final_green_s),
        "final_fitness": dict(result.final_fitness),
    }


def write_transition_result(result, scenario, policy, destination: str | Path) -> None:
    from green_wave.models.errors import ConfigurationError
    from green_wave.visualization.convergence import render_convergence_svg
    from green_wave.visualization.signal_timeline import render_signal_svg

    path = Path(destination)
    if path.exists():
        raise ConfigurationError(f"el directorio de resultados ya existe: {path}")
    path.mkdir(parents=True)
    effective = {
        "scenario_id": scenario.id,
        "h_inicio_s": scenario.h_inicio_s,
        "intersections": {key: {"cycle_s": item.cycle_s, "yellow_s": item.yellow_s}
                          for key, item in scenario.intersections.items()},
        "plan_a_green_s": {key: item.green_s for key, item in scenario.plan_a.entries.items()},
        "plan_b_green_s": {key: item.green_s for key, item in scenario.plan_b.entries.items()},
        "plan_a_green_origins_s": dict(policy.plan_a_green_origins_s),
        "plan_b_green_origins_s": dict(policy.plan_b_green_origins_s),
        "boundary_metric": policy.boundary_metric,
        "application_policy": policy.application,
        "cycle_limit_scope": policy.cycle_limit_scope,
        "max_transition_cycles": scenario.transition.max_transition_cycles,
        "optimizer_parameters": dict(result.optimizer_parameters),
    }
    (path / "run.json").write_text(json.dumps(result_data(result), ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    (path / "effective_config.json").write_text(json.dumps(effective, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    for key, trace in result.traces.items():
        write_trace(trace, path / f"trace_{key}.json")
    with (path / "transitions.csv").open("w", encoding="utf-8", newline="") as stream:
        columns = ("intersection_id", "local_cycle", "applied_at_s", "previous_green_s",
                   "next_green_s", "previous_fitness", "next_fitness",
                   "optimizer_generations", "evaluated_candidates", "optimizer_reason")
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for step in result.steps:
            writer.writerow({column: getattr(step, column) for column in columns})
    with (path / "phase_events.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("intersection_id", "time_s", "previous", "next"))
        for key, trace in result.traces.items():
            for event in trace.changes:
                writer.writerow((key, event.time_s, event.previous.value, event.next.value))
    (path / "signals.svg").write_text(render_signal_svg(result, dict(policy.plan_a_green_origins_s),
                                                       dict(policy.plan_b_green_origins_s)), encoding="utf-8")
    (path / "fitness.svg").write_text(render_convergence_svg(result), encoding="utf-8")
