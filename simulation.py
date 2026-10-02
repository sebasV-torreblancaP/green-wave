"""Preparación común de la simulación diaria para ambas vistas."""
from day_simulation import simulate_day


def prepare_simulation(cfg):
    """Genera el día nominal, solicita la Wave exacta y conserva el resultado."""
    settings = cfg.get('day',{})
    day = simulate_day(start=settings.get('start','06:00'),end=settings.get('end','22:00'),
                       wave=settings.get('initial_wave','A'),config=cfg)
    requests = settings.get('requests')
    if requests is None:
        requests = [dict(time=settings.get('transition_time','13:37:24'),
                         from_wave=settings.get('initial_wave','A'),to_wave=settings.get('target_wave','B'))]
    for request in requests:
        day.transition(request['time'],request.get('from_wave',day.active_wave_at(request['time'])),request['to_wave'])
    return day.simulate_remaining_day()
