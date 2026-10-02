"""Simulación diaria con solicitudes desde el estado real de los controladores.

Un ciclo G→A→R de C segundos conserva su inicio módulo C. La duración y la
corrección de offset son decisiones diferentes; un objetivo incompatible se
registra como FAILED sin interrumpir fases ni sustituir la Wave solicitada.
"""
import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta
import math

from continuous import LocalCycle, controller_state_at, cycle_events
from green_wave import (Intersection, WavePlan, assess_phase_offset, calculate_wave_plan,
                        choose_nominal_green, whole_seconds)
from timeline import frames_from_events


def build_waves(cfg, intersections):
    cycle = cfg['cycle']['common_cycle_s']
    corridor = cfg['corridor']
    definitions = cfg.get('waves', {})
    plans = {}
    for name, direction, speed in (('A','up',corridor['speed_up_kmh']),
                                    ('B','down',corridor['speed_down_kmh'])):
        definition = definitions.get(name, {})
        direction, speed = definition.get('direction',direction), definition.get('speed_kmh',speed)
        reference = definition.get('reference_offset_s', cfg['initial_offsets_s'][0])
        plan = calculate_wave_plan(intersections,cycle,speed,direction,reference)
        offsets = definition.get('offsets_s')
        if offsets is None and name == 'A' and corridor.get('up_offsets_mode') == 'manual':
            offsets = cfg['initial_offsets_s']
        if offsets is not None:
            if len(offsets) != len(intersections):
                raise ValueError(f'Wave {name}: falta un offset por intersección.')
            plan = WavePlan(direction,speed,[whole_seconds(o,f'waves.{name}.offsets_s') % cycle for o in offsets])
        plans[name] = plan
    return plans


@dataclass
class DayTransition:
    transition_start_s: int
    transition_end_s: int
    from_wave: str
    to_wave: str
    status: str
    reason: str
    target_achievable: bool
    transition_cycles: int
    initial_state: list
    target_state: list
    final_state: list
    offset_corrections: list
    decisions: list = field(default_factory=list)
    intersections: list = field(default_factory=list)

    @property
    def transition_complete(self):
        return self.status == 'SUCCESS'

    @property
    def transition_duration_s(self):
        return self.transition_end_s-self.transition_start_s

    def metrics(self):
        return dict(asdict(self), transition_duration_s=self.transition_duration_s,
                    transition_complete=self.transition_complete,
                    assessment='TARGET ACHIEVABLE' if self.target_achievable else
                               'TARGET NOT ACHIEVABLE UNDER CURRENT CONSTRAINTS')


class DaySimulation:
    def __init__(self, cfg, start='06:00', end='22:00', wave='A', controller_cycles=None):
        self.config = copy.deepcopy(cfg)
        self.cycle_s = whole_seconds(cfg['cycle']['common_cycle_s'],'common_cycle_s')
        self.amber_s = whole_seconds(cfg['cycle']['yellow_s'],'yellow_s')
        if self.cycle_s <= 0 or self.amber_s <= 0:
            raise ValueError('La simulación diaria requiere ciclo y ámbar positivos.')
        self.nominal_green_s = tuple(whole_seconds(g,'green_nominal') for g in cfg['cycle']['green_base_s'])
        self.nominal_red_s = tuple(self.cycle_s-g-self.amber_s for g in self.nominal_green_s)
        self.intersections = [Intersection(x['id'],float(x['distance_from_s1_m'])) for x in cfg['intersections']]
        if len(self.intersections) != len(self.nominal_green_s) or len({x.id for x in self.intersections}) != len(self.intersections):
            raise ValueError('IDs únicos y un verde nominal por intersección.')
        self.waves = build_waves(self.config,self.intersections)
        if wave not in self.waves:
            raise ValueError(f'Wave inicial desconocida: {wave}.')
        self.initial_wave = wave
        date = cfg.get('day',{}).get('date','2026-10-02')
        self.start_datetime = datetime.combine(datetime.fromisoformat(date).date(),time.fromisoformat(start))
        self.requested_end_datetime = datetime.combine(self.start_datetime.date(),time.fromisoformat(end))
        if self.requested_end_datetime <= self.start_datetime:
            self.requested_end_datetime += timedelta(days=1)
        self.requested_duration_s = int((self.requested_end_datetime-self.start_datetime).total_seconds())
        minimum = whole_seconds(cfg.get('simulation',{}).get('min_duration_s',0),'min_duration_s')
        self.total_s = math.ceil(max(self.requested_duration_s,minimum)/self.cycle_s)*self.cycle_s
        self.requests = []
        # La Wave A de todo el día se genera antes de calcular una transición.
        nominal = self._nominal_cycles(self.total_s)
        self.cycles = nominal if controller_cycles is None else list(controller_cycles)
        self.initial_state_source = 'nominal_wave' if controller_cycles is None else 'controller_history'
        self._validate_cycles(self.cycles,self.total_s)
        self.baseline_cycles = list(self.cycles)
        self.baseline_states = cycle_events(self.baseline_cycles,self.total_s,self.cycle_s)
        self._refresh()

    def _limit_arguments(self, i):
        limits = self.config['transition']
        maximum = limits.get('max_green_s',self.cycle_s-self.amber_s-limits.get('min_red_s',1))
        if isinstance(maximum,list):
            if len(maximum) != len(self.intersections):
                raise ValueError('max_green_s debe tener un valor por intersección.')
            maximum = maximum[i]
        return dict(fraction=limits['max_green_change_fraction_per_cycle'],
                    min_green_s=limits.get('min_green_s',1), max_green_s=maximum,
                    min_red_s=limits.get('min_red_s',1), green_step_s=limits.get('green_step_s'))

    def _validate_cycles(self, cycles, total):
        identities = {x.id for x in self.intersections}
        if {c.intersection_id for c in cycles} != identities:
            raise ValueError('El histórico no contiene exactamente los controladores configurados.')
        cycle_events(cycles,total,self.cycle_s)
        by_id = {x.id:i for i,x in enumerate(self.intersections)}
        for c in cycles:
            i = by_id[c.intersection_id]
            if c.yellow_s != self.amber_s:
                raise ValueError('El ámbar físico no coincide con la configuración nominal.')
            choose_nominal_green(c.green_s,self.nominal_green_s[i],self.cycle_s,self.amber_s,
                                  **self._limit_arguments(i))

    def _nominal_cycles(self, total):
        count = total//self.cycle_s
        return [LocalCycle(inter.id,offset+k*self.cycle_s,self.nominal_green_s[i],
                           self.amber_s,self.nominal_red_s[i],f'wave_{self.initial_wave}')
                for i,(inter,offset) in enumerate(zip(self.intersections,self.waves[self.initial_wave].offsets_s))
                for k in range(-1,count)]

    def seconds(self, value):
        if isinstance(value,(int,float)) and not isinstance(value,bool):
            return whole_seconds(value,'time_s')
        if isinstance(value,datetime):
            moment = value
        elif 'T' in str(value):
            moment = datetime.fromisoformat(str(value))
        else:
            moment = datetime.combine(self.start_datetime.date(),time.fromisoformat(str(value)))
            if moment < self.start_datetime:
                moment += timedelta(days=1)
        return int((moment-self.start_datetime).total_seconds())

    def timestamp(self, seconds):
        return (self.start_datetime+timedelta(seconds=seconds)).isoformat(timespec='seconds')

    def active_wave_at(self, value):
        t = self.seconds(value)
        active = self.initial_wave
        for request in self.requests:
            if request.status == 'SUCCESS' and request.transition_end_s <= t:
                active = request.to_wave
        return active

    def state_at(self, value):
        t = self.seconds(value)
        if not 0 <= t < self.total_s:
            raise ValueError('La consulta está fuera del horizonte guardado.')
        active = self.active_wave_at(t)
        return [dict(s,timestamp=self.timestamp(t),wave_id=active) for s in controller_state_at(self.cycles,t)]

    def _stage_at(self, t):
        for request in self.requests:
            if request.status == 'SUCCESS' and request.transition_start_s <= t < request.transition_end_s:
                return 'transicion'
        return f'wave_{self.active_wave_at(t)}'

    def _refresh(self):
        self.states = cycle_events(self.cycles,self.total_s,self.cycle_s)
        offsets = [next(c.start_s % self.cycle_s for c in self.cycles if c.intersection_id == x.id)
                   for x in self.intersections]
        self.frames = frames_from_events(self.intersections,self.cycle_s,self.total_s,offsets,self.states,self._stage_at)

    def _extend(self, required):
        new_total = math.ceil(required/self.cycle_s)*self.cycle_s
        if new_total <= self.total_s:
            return
        extended = []
        for intersection in self.intersections:
            own = sorted((c for c in self.cycles if c.intersection_id == intersection.id),key=lambda c:c.start_s)
            last = own[-1]
            while last.end_s < new_total:
                last = LocalCycle(last.intersection_id,last.end_s,last.green_s,last.yellow_s,last.red_s,last.stage)
                own.append(last)
            extended.extend(own)
        self.cycles = extended
        # Conserva el histórico real previo y continúa su último estado periódico.
        baseline = []
        for intersection in self.intersections:
            own = sorted((c for c in self.baseline_cycles if c.intersection_id == intersection.id),key=lambda c:c.start_s)
            last = own[-1]
            while last.end_s < new_total:
                last = LocalCycle(last.intersection_id,last.end_s,last.green_s,last.yellow_s,last.red_s,last.stage)
                own.append(last)
            baseline.extend(own)
        self.baseline_cycles = baseline
        self.total_s = new_total
        self.baseline_states = cycle_events(baseline,new_total,self.cycle_s)

    def transition(self, time, from_wave='A', to_wave='B'):
        t = self.seconds(time)
        if not 0 <= t < self.requested_duration_s:
            raise ValueError('La solicitud debe estar dentro del día configurado.')
        if from_wave not in self.waves or to_wave not in self.waves:
            raise ValueError('Wave de origen u objetivo desconocida.')
        if self.requests and t < self.requests[-1].transition_start_s:
            raise ValueError('Las solicitudes deben introducirse en orden cronológico.')
        initial = self.state_at(t)
        target_plan = self.waves[to_wave]
        corrections = [asdict(assess_phase_offset(s['offset_s'],offset,self.cycle_s))
                       for s,offset in zip(initial,target_plan.offsets_s)]
        target = [dict(intersection_id=x.id,offset_s=offset,green_s=self.nominal_green_s[i],
                       amber_s=self.amber_s,red_s=self.nominal_red_s[i])
                  for i,(x,offset) in enumerate(zip(self.intersections,target_plan.offsets_s))]
        achievable = all(c['achievable'] for c in corrections)
        reason = 'TARGET ACHIEVABLE' if achievable else corrections[next(i for i,c in enumerate(corrections) if not c['achievable'])]['reason']
        if self.active_wave_at(t) != from_wave:
            achievable, reason = False, 'SOURCE_WAVE_MISMATCH: la Wave de origen no está activa a esa hora.'
        if any(r.status == 'SUCCESS' and r.transition_start_s <= t < r.transition_end_s for r in self.requests):
            achievable, reason = False, 'TRANSITION_IN_PROGRESS: ya existe una transición física en curso.'
        decisions, local_counts, restored_at = [], [], []
        if achievable:
            try:
                for i,(s,intersection) in enumerate(zip(initial,self.intersections)):
                    current = s['green_s']
                    next_start = s['cycle_start_s'] if t == s['cycle_start_s'] else s['cycle_end_s']
                    count = 0
                    while current != self.nominal_green_s[i]:
                        if count >= self.config['transition']['max_transition_cycles']:
                            raise ValueError('MAX_TRANSITION_CYCLES: la restauración necesita más ciclos permitidos.')
                        selected, adjustment = choose_nominal_green(current,self.nominal_green_s[i],
                                                                     self.cycle_s,self.amber_s,**self._limit_arguments(i))
                        decisions.append(dict(intersection_id=intersection.id,time_s=next_start,
                                              green_before_s=current,green_s=selected,amber_s=self.amber_s,
                                              red_s=self.cycle_s-selected-self.amber_s,
                                              offset_s=s['offset_s'],target_offset_s=target_plan.offsets_s[i],
                                              offset_error_s=corrections[i]['requested_s'],
                                              green_error_before_s=self.nominal_green_s[i]-current,
                                              green_error_s=self.nominal_green_s[i]-selected,
                                              phase_duration_adjustment=asdict(adjustment),
                                              phase_offset_correction=corrections[i]))
                        current = selected
                        count += 1
                        restored = next_start
                        next_start += self.cycle_s
                    local_counts.append(count)
                    restored_at.append(restored if count else t)
            except ValueError as exc:
                achievable, reason, decisions = False, str(exc), []
        end = max(restored_at,default=t) if achievable else t
        status = 'SUCCESS' if achievable else 'FAILED'
        request = DayTransition(t,end,from_wave,to_wave,status,reason,achievable,
                                max(local_counts,default=0) if achievable else 0,
                                initial,target,[],corrections,sorted(decisions,key=lambda d:(d['time_s'],d['intersection_id'])))
        if achievable:
            post = whole_seconds(self.config.get('day',{}).get('post_transition_s',3600),'post_transition_s')
            if post < 3600:
                raise ValueError('day.post_transition_s debe permitir al menos 60 minutos estables.')
            self._extend(end+post)
            adjusted = []
            for i,intersection in enumerate(self.intersections):
                commands = {d['time_s']:d['green_s'] for d in decisions if d['intersection_id'] == intersection.id}
                current = initial[i]['green_s']
                for c in sorted((c for c in self.cycles if c.intersection_id == intersection.id),key=lambda c:c.start_s):
                    if c.start_s < t:
                        adjusted.append(c)
                        continue
                    current = commands.get(c.start_s,current)
                    stage = f'wave_{to_wave}' if c.start_s >= end else 'transicion'
                    adjusted.append(LocalCycle(c.intersection_id,c.start_s,current,self.amber_s,
                                                self.cycle_s-current-self.amber_s,stage))
            self.cycles = adjusted
        self.requests.append(request)
        self._refresh()
        request.final_state = self.state_at(end)
        for i,s in enumerate(initial):
            own = [d for d in decisions if d['intersection_id'] == s['intersection_id']]
            greens = [s['green_s']]+[d['green_s'] for d in own]
            deviations = [g-self.nominal_green_s[i] for g in greens]
            request.intersections.append(dict(intersection_id=s['intersection_id'],initial_green=s['green_s'],
                final_green_during_transition=greens[-1],nominal_green=self.nominal_green_s[i],
                final_green=request.final_state[i]['green_s'],
                max_green_deviation=max(deviations),min_green_deviation=min(deviations),
                max_absolute_green_deviation=max(map(abs,deviations)),
                initial_offset=s['offset_s'],target_offset=target_plan.offsets_s[i],
                final_offset=request.final_state[i]['offset_s'],local_transition_cycles=len(own)))
        return request

    def simulate_remaining_day(self):
        self._refresh()
        return self

    def metadata(self):
        return dict(model='day_fixed_physical_cycles',simulation_start=self.start_datetime.isoformat(),
                    requested_end=self.requested_end_datetime.isoformat(),
                    simulated_end=self.timestamp(self.total_s),requested_duration_s=self.requested_duration_s,
                    audit_horizon_extension_s=self.total_s-self.requested_duration_s,
                    timestamp_convention='Hora local de simulación; segundos relativos a simulation_start.',
                    initial_state_source=self.initial_state_source,initial_wave=self.initial_wave,
                    nominal_green_s=list(self.nominal_green_s),nominal_red_s=list(self.nominal_red_s),
                    waves={name:plan.parameters(self.intersections) for name,plan in self.waves.items()},
                    transitions=[dict(r.metrics(),transition_start=self.timestamp(r.transition_start_s),
                                      transition_end=self.timestamp(r.transition_end_s)) for r in self.requests])

    def export(self, root):
        from history import export_day_history
        return export_day_history(root,self)


def simulate_day(start='06:00', end='22:00', wave='A', config=None, controller_cycles=None):
    if config is None:
        import json
        from pathlib import Path
        config = json.loads((Path(__file__).resolve().parent/'config.json').read_text(encoding='utf-8'))
    return DaySimulation(config,start,end,wave,controller_cycles)
