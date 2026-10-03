import argparse
import json
import sys

from green_wave.configuration.loader import load_scenario
from green_wave.models.errors import GreenWaveError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Herramientas de validación Green Wave")
    parser.add_argument("scenario", help="ruta al archivo scenario.json")
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--validate", action="store_true", help="validar configuración y restricciones físicas")
    command.add_argument("--domain", metavar="ID", help="mostrar el siguiente dominio de G para una intersección")
    command.add_argument("--preview", metavar="ID", help="mostrar una señal fija con origen verde explícito")
    command.add_argument("--run-reference", action="store_true", help="ejecutar el prototipo con política explícita")
    command.add_argument("--run-genetic", action="store_true", help="ejecutar GA con operadores explícitos")
    parser.add_argument("--green-origin-s", type=int, help="inicio absoluto del verde para --preview")
    parser.add_argument("--plan", choices=("A", "B"), help="plan a visualizar con --preview")
    parser.add_argument("--duration-s", type=int, help="duración de --preview; por defecto un ciclo")
    parser.add_argument("--origins", help="JSON con orígenes de verde de A y B para --run-reference")
    parser.add_argument("--boundary-metric", choices=("circular", "linear"),
                        help="métrica explícita de fronteras para --run-reference")
    parser.add_argument("--genetic-choices", help="JSON con operadores, mutación y semilla para --run-genetic")
    parser.add_argument("--output", help="directorio nuevo para guardar --run-reference")
    args = parser.parse_args(argv)
    try:
        scenario = load_scenario(args.scenario)
        if args.validate:
            print(json.dumps({"scenario": scenario.id, "intersections": len(scenario.intersections),
                              "status": "structurally_valid", "temporal_contract": "unresolved"},
                             ensure_ascii=False))
        elif args.domain:
            from green_wave.mathematics.feasible_domain import next_green_domain
            intersection = scenario.intersections.get(args.domain)
            if intersection is None:
                parser.error(f"intersección desconocida: {args.domain}")
            current = scenario.plan_a.entries[args.domain].green_s
            domain = next_green_domain(intersection, current, scenario.transition.max_green_change_percent)
            print(json.dumps({"intersection": args.domain, "current_green_s": current,
                              "lower": domain.lower, "upper": domain.upper, "count": len(domain)}))
        elif args.preview:
            from green_wave.simulation.signal_simulator import simulate_fixed_signal
            from green_wave.visualization.signal_timeline import render_text_timeline
            if args.green_origin_s is None or args.plan is None:
                parser.error("--preview requiere --green-origin-s y --plan")
            intersection = scenario.intersections.get(args.preview)
            if intersection is None:
                parser.error(f"intersección desconocida: {args.preview}")
            plan = scenario.plan_a if args.plan == "A" else scenario.plan_b
            green = plan.entries[args.preview].green_s
            duration = args.duration_s if args.duration_s is not None else intersection.cycle_s
            trace = simulate_fixed_signal(intersection, green, green_origin_s=args.green_origin_s,
                                          start_s=scenario.h_inicio_s, duration_s=duration)
            print(render_text_timeline(trace))
        else:
            from green_wave.algorithms.transition_engine import run_genetic, run_reference
            from green_wave.configuration.loader import load_genetic_choices, load_reference_policy
            from green_wave.persistence.result_writer import result_data, write_transition_result
            if args.origins is None or args.boundary_metric is None:
                parser.error("la transición requiere --origins y --boundary-metric")
            policy = load_reference_policy(args.origins, scenario, args.boundary_metric)
            if args.run_genetic:
                if args.genetic_choices is None:
                    parser.error("--run-genetic requiere --genetic-choices")
                choices = load_genetic_choices(args.genetic_choices)
                result = run_genetic(scenario, policy, choices)
            else:
                result = run_reference(scenario, policy)
            if args.output is not None:
                write_transition_result(result, scenario, policy, args.output)
            print(json.dumps(result_data(result), ensure_ascii=False))
        return 0
    except GreenWaveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
