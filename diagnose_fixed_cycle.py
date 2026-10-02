"""Evalúa offsets exactos desde una hora real; nunca sustituye Wave B."""
import argparse
import json

from main import load_config,validate_config
from simulation import prepare_simulation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='config.json')
    parser.add_argument('--at',help='Hora de solicitud HH:MM:SS')
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.at:
        cfg.setdefault('day',{})['transition_time'] = args.at
    validate_config(cfg)
    day = prepare_simulation(cfg)
    result = dict(nominal_green_s=list(day.nominal_green_s),nominal_red_s=list(day.nominal_red_s),
                  waves=day.metadata()['waves'],transitions=[r.metrics() for r in day.requests])
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 2 if any(r.status == 'FAILED' for r in day.requests) else 0


if __name__ == '__main__':
    raise SystemExit(main())
