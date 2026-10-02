"""Segunda vista de la misma simulación diaria y del mismo histórico físico."""
import argparse
from pathlib import Path

from main import load_config,validate_config
from simulation import prepare_simulation
from visualization import plot_day_timeline,plot_day_transition_metrics
from history import print_audit
from verify_fixed_cycle import verify_fixed_cycle_history

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config.json')
    parser.add_argument('--no-show',action='store_true')
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--transition-time')
    parser.add_argument('--duration-s',type=int)
    args = parser.parse_args()
    cfg = load_config(args.config)
    cfg.setdefault('day',{})
    for key,value in (('start',args.start),('end',args.end),('transition_time',args.transition_time)):
        if value is not None:
            cfg['day'][key] = value
    if args.duration_s is not None:
        cfg['simulation']['min_duration_s'] = args.duration_s
    validate_config(cfg)
    day = prepare_simulation(cfg)
    run,audit = day.export(ROOT/'historico')
    print_audit(run,audit)
    print(verify_fixed_cycle_history(run))
    for request in day.requests:
        print(f'{request.status}: {request.reason}')
    plot_day_timeline(day,ROOT/'semaphore_cycles.png',show=not args.no_show)
    plot_day_timeline(day,ROOT/'day_transition_detail.png',show=not args.no_show,zoom=True)
    plot_day_transition_metrics(day,ROOT/'transition.png',show=not args.no_show)
    import shutil
    for name in ('semaphore_cycles.png','day_transition_detail.png','transition.png'):
        shutil.copy2(ROOT/name,run/name)
    return 2 if any(r.status == 'FAILED' for r in day.requests) else 0


if __name__ == '__main__':
    raise SystemExit(main())
