"""Ensayo separado de recuperación nominal desde un histórico real temporal.

Declara explícitamente un objetivo con offsets compatibles. No demuestra ni
afirma una reversión a los offsets originales de BAJADA, que son incompatibles.
"""
import copy
from pathlib import Path

from continuous import LocalCycle
from day_simulation import simulate_day
from main import load_config,validate_config
from visualization import plot_day_timeline,plot_day_transition_metrics
from verify_day import verify_day_history

ROOT = Path(__file__).resolve().parent


def main():
    cfg = copy.deepcopy(load_config(ROOT/'config.day.example.json'))
    cfg['day'].update(start='06:00',end='08:00',transition_time='06:16:15',
                       validation_case='nominal_recovery_with_explicitly_compatible_offsets')
    cfg['waves']['B'] = copy.deepcopy(cfg['waves']['A'])
    validate_config(cfg)
    nominal = simulate_day(config=cfg,start='06:00',end='08:00')
    initial = nominal.state_at('06:16:15')
    deviations = [-2,3,-1,1,0,0]
    imported = []
    for i,intersection in enumerate(nominal.intersections):
        deviation = deviations[i]
        # El histórico importado incluye los ajustes previos: cada paso es
        # de 1 s, con rojo compensado y sin mover ningún inicio físico.
        begin = initial[i]['cycle_start_s']-(abs(deviation)-1)*140
        for c in (c for c in nominal.cycles if c.intersection_id == intersection.id):
            progress = min(abs(deviation),max(0,(c.start_s-begin)//140+1))
            green = c.green_s+(1 if deviation >= 0 else -1)*progress
            imported.append(LocalCycle(c.intersection_id,c.start_s,green,3,137-green,c.stage))
    day = simulate_day(config=cfg,start='06:00',end='08:00',controller_cycles=imported)
    result = day.transition('06:16:15',from_wave='A',to_wave='B')
    day.simulate_remaining_day()
    run,audit = day.export(ROOT/'historico')
    proof = verify_day_history(run)
    plot_day_timeline(day,run/'day_timeline.png',show=False)
    plot_day_timeline(day,run/'day_transition_detail.png',show=False,zoom=True)
    plot_day_transition_metrics(day,run/'transition.png',show=False)
    print('RESTORATION TEST WITH EXPLICITLY COMPATIBLE OFFSETS')
    print(f'{result.status}: {result.reason}; {result.transition_duration_s} s; {result.transition_cycles} ciclos.')
    print(f'Histórico: {run}')
    print(f"Auditoría: {audit['nonconstant_cycles']} ciclos anómalos; {len(audit['sequence_issues'])} secuencias inválidas.")
    print(proof)
    return 0 if result.status == 'SUCCESS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
