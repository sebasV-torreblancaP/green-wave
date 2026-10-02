from typing import List
import math
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from matplotlib.ticker import FuncFormatter
from green_wave import Intersection, WavePlan, TransitionResult, travel_time_s
from timeline import phase_segments, build_timeline


COLORS = {"green": "#00d52b", "yellow": "#ffc928", "red": "#ff2525"}


def green_departure_windows(intersections, plan, greens, cycle):
    """Intersección exacta de ventanas de salida que llegan en verde a todos."""
    source = intersections[0] if plan.direction == "up" else intersections[-1]
    windows = [(0.0, cycle)]
    for inter, offset, green in zip(intersections, plan.offsets_s, greens):
        travel = travel_time_s(abs(inter.distance_m - source.distance_m), plan.speed_kmh)
        allowed = [(a, b) for phase, a, b in phase_segments(
            offset - travel, green, 0, cycle, 0, cycle) if phase == "green"]
        windows = [(max(a, c), min(b, d)) for a, b in windows for c, d in allowed
                   if min(b, d) > max(a, c)]
    return windows


def plot_corridor(
    intersections: List[Intersection], cycle_s: float, green_base_s: List[float],
    up_plan: WavePlan, down_plan: WavePlan, transition: TransitionResult,
    cycles_up: int, cycles_down: int,
    speed_up_kmh: float, speed_down_kmh: float,
    save_path: str = "green_wave.png", yellow_s: float = 4.0,
    vehicle_start_offset_s: float = 0.0, trajectories_per_cycle: int = 5,
    show: bool = True, state_history=None, audit_report=None,
):
    transition_cycles = transition.cycles_used
    up_end = cycles_up * cycle_s
    down_start = up_end + transition_cycles * cycle_s
    total_s = down_start + cycles_down * cycle_s
    distances = [inter.distance_m for inter in intersections]
    span = distances[-1] - distances[0]
    width = min(b - a for a, b in zip(distances, distances[1:])) * 0.045
    fig, ax = plt.subplots(figsize=(13, 12))

    ax.axhspan(up_end, down_start, facecolor="#c4b5fd", alpha=0.6, zorder=0)
    if state_history is None:
        _, state_history = build_timeline(intersections, cycle_s, yellow_s, green_base_s,
                                          up_plan, transition, cycles_up, cycles_down)
    positions = {inter.id: inter.distance_m for inter in intersections}
    for row in state_history:
        ax.add_patch(Rectangle((positions[row['intersection_id']] - width / 2, row['start_s']),
                               width, row['duration_s'], facecolor=COLORS[row['state']],
                               edgecolor="none", zorder=3))

    def draw_wave(plan, start, end, offsets):
        plan_greens = transition.final_green_s if plan.direction == 'down' else green_base_s
        plan_greens = plan_greens or green_base_s
        source = distances[0] if plan.direction == "up" else distances[-1]
        travels = [travel_time_s(abs(d - source), plan.speed_kmh) for d in distances]
        windows = green_departure_windows(
            intersections, WavePlan(plan.direction, plan.speed_kmh, offsets),
            plan_greens, cycle_s)
        # La banda es el conjunto de salidas que cruza todo el corredor en verde.
        for k in range(int((end - start) / cycle_s)):
            for a, b in windows:
                departure_a, departure_b = start + k * cycle_s + a, start + k * cycle_s + b
                if departure_b + max(travels) <= end:
                    ax.fill_between(distances, [departure_a + t for t in travels],
                                    [departure_b + t for t in travels],
                                    color=COLORS["green"], alpha=0.10, zorder=1)
            for j in range(trajectories_per_cycle):
                departure = start + k * cycle_s + (
                    vehicle_start_offset_s + j * cycle_s / trajectories_per_cycle) % cycle_s
                arrivals = [departure + t for t in travels]
                if max(arrivals) > end:
                    continue
                passes = all((t - offset) % cycle_s < green
                             for t, offset, green in zip(arrivals, offsets, plan_greens))
                ax.plot(distances, arrivals, "--", linewidth=1.1,
                        color="#00b987" if passes else "#525252", alpha=0.85, zorder=2)
        return sum(b - a for a, b in windows)

    up_band = draw_wave(up_plan, 0, up_end, up_plan.offsets_s)
    down_band = draw_wave(down_plan, down_start, total_s, transition.final_offsets_s)
    for a, b, label in [(0, up_end, "SUBIDA"), (up_end, down_start, "TRANSICIÓN"),
                        (down_start, total_s, "BAJADA")]:
        if b <= a:
            continue
        ax.text(distances[-1] + span * 0.05, (a + b) / 2, label,
                rotation=90, va="center", fontsize=10, fontweight="bold")
    for boundary, label, vertical in ((up_end, "Inicio", "top"), (down_start, "Fin", "bottom")):
        ax.axhline(boundary, color="#6d28d9", linestyle="--", linewidth=2)
        ax.text(0.02, boundary, f"{label} transición: {boundary:g} s",
                transform=ax.get_yaxis_transform(), va=vertical, color="#5b21b6", zorder=5,
                bbox=dict(facecolor="white", edgecolor="#6d28d9", alpha=0.95))
    tick_step = max(1, math.ceil(total_s / cycle_s / 24))
    ax.set_yticks([k * cycle_s for k in range(0, round(total_s / cycle_s) + 1, tick_step)])
    ax.set_xlim(distances[0] - span * 0.04, distances[-1] + span * 0.10)
    ax.set_ylim(0, total_s)
    ax.set_xticks(distances, [f"{i.id}\n{i.distance_m:g} m" for i in intersections])
    ax.set_xlabel("Distancia acumulada desde la primera intersección (m)")
    ax.set_ylabel("Tiempo desde el inicio (s) ↑")
    ax.set_title(f"Ola verde — {len(intersections)} semáforos\n"
                 f"Subida: {speed_up_kmh:g} km/h · Bajada: {speed_down_kmh:g} km/h\n"
                 f"Ventana de salida en verde: subida ≈{up_band:.0f} s · bajada ≈{down_band:.0f} s")
    if audit_report is not None:
        ax.set_title(ax.get_title() + f"\nAuditoría: {audit_report['nonconstant_cycles']} ciclos observados "
                     f"distintos de {cycle_s:g} s")
    handles = [Patch(color=COLORS[p], label=label) for p, label in
               [("green", "Verde"), ("yellow", "Amarillo"), ("red", "Rojo")]]
    handles += [Line2D([0], [0], color="#00b987", linestyle="--", label="Cruza todos en verde"),
                Line2D([0], [0], color="#525252", linestyle="--", label="Encuentra amarillo o rojo")]
    handles.append(Patch(color="#c4b5fd", label=f"Transición: {transition_cycles} ciclos"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.075), ncol=3)
    ax.grid(axis="y", alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, dpi=160, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def _day_limits(day,zoom):
    if not zoom or not day.requests:
        return 0,day.total_s
    first,last = day.requests[0].transition_start_s,max(r.transition_end_s for r in day.requests)
    return max(0,first-2*day.cycle_s),min(day.total_s,last+3*day.cycle_s)


def _day_annotations(ax,day,left,right):
    active,start = day.initial_wave,0
    for request in day.requests:
        t,end = request.transition_start_s,request.transition_end_s
        if request.status == 'SUCCESS':
            if t > start and min(t,right) > max(start,left):
                ax.axvspan(max(start,left),min(t,right),color='#dcfce7',alpha=.35,zorder=-2)
                ax.text((max(start,left)+min(t,right))/2,.98,f'WAVE {active}',
                        transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=10)
            if end > t:
                ax.axvspan(t,end,color='#c4b5fd',alpha=.35,zorder=-1)
                ax.text((t+end)/2,.98,'TRANSICIÓN',transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=10)
            active,start = request.to_wave,end
        if left <= t <= right:
            ax.axvline(t,color='#b91c1c' if request.status == 'FAILED' else '#6d28d9',linestyle='--',linewidth=1.6)
            ax.annotate(f"{day.timestamp(t)[11:]} · {request.from_wave}→{request.to_wave}\n{request.status}",
                        xy=(t,0),xycoords=ax.get_xaxis_transform(),xytext=(5,-32),textcoords='offset points',
                        ha='left',va='top',fontsize=8,color='#b91c1c' if request.status == 'FAILED' else '#5b21b6')
    if right > max(start,left):
        ax.axvspan(max(start,left),right,color='#dbeafe' if active != day.initial_wave else '#dcfce7',alpha=.35,zorder=-2)
        ax.text((max(start,left)+right)/2,.98,f'WAVE {active}',transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=10)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value,_:day.timestamp(value)[11:19]))


def plot_day_timeline(day,save_path='green_wave.png',show=True,zoom=False):
    if not show:
        plt.switch_backend('Agg')
    left,right = _day_limits(day,zoom)
    fig,ax = plt.subplots(figsize=(17,7))
    for i,intersection in enumerate(day.intersections):
        y = len(day.intersections)-1-i
        for phase,color in COLORS.items():
            ranges = [(max(left,r['start_s']),min(right,r['end_s'])-max(left,r['start_s']))
                      for r in day.states if r['intersection_id'] == intersection.id and r['state'] == phase
                      and min(right,r['end_s']) > max(left,r['start_s'])]
            ax.broken_barh(ranges,(y-.32,.64),facecolors=color,edgecolors='black',linewidths=.15)
    _day_annotations(ax,day,left,right)
    ax.set_xlim(left,right)
    ax.set_ylim(-.7,len(day.intersections)-.3)
    ax.set_yticks(range(len(day.intersections)),[x.id for x in reversed(day.intersections)])
    ax.set_xlabel('Hora local de simulación')
    ax.set_ylabel('Intersección')
    outcome = '; '.join(r.status for r in day.requests) or 'SIN SOLICITUD'
    ax.set_title(f'Wave A / solicitud / estado posterior · {outcome}\n'
                 f'Ciclo físico {day.cycle_s} s · ámbar {day.amber_s} s · duraciones nominales independientes')
    ax.legend(handles=[Patch(color=COLORS[p],label=l) for p,l in
                       (('green','Verde'),('yellow','Ámbar'),('red','Rojo'))],loc='upper right')
    ax.grid(axis='x',alpha=.2)
    fig.subplots_adjust(bottom=.2,top=.82)
    fig.savefig(save_path,dpi=160,bbox_inches='tight')
    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_day_transition_metrics(day,save_path='transition.png',show=True):
    if not show:
        plt.switch_backend('Agg')
    left,right = _day_limits(day,True)
    fig,axes = plt.subplots(5,1,figsize=(15,13),sharex=True)
    target = day.waves[day.requests[-1].to_wave] if day.requests else day.waves[day.initial_wave]
    for i,intersection in enumerate(day.intersections):
        own = sorted((c for c in day.cycles if c.intersection_id == intersection.id
                       and c.end_s > left and c.start_s < right),key=lambda c:c.start_s)
        if not own:
            continue
        x = [c.start_s for c in own]+[own[-1].end_s]
        line, = axes[0].step(x,[c.green_s for c in own]+[own[-1].green_s],where='post',label=intersection.id)
        color = line.get_color()
        axes[0].axhline(day.nominal_green_s[i],color=color,linestyle=':',alpha=.5)
        axes[1].step(x,[c.red_s for c in own]+[own[-1].red_s],where='post',color=color)
        axes[2].step(x,[c.start_s % day.cycle_s for c in own]+[own[-1].start_s % day.cycle_s],where='post',color=color)
        axes[2].axhline(target.offsets_s[i],color=color,linestyle='--',alpha=.65)
        axes[3].step(x,[c.yellow_s for c in own]+[own[-1].yellow_s],where='post',color=color)
        axes[4].step(x,[c.duration_s for c in own]+[own[-1].duration_s],where='post',color=color)
    for ax,label in zip(axes,('Verde (s)','Rojo (s)','Offset (s)\nobjetivo discontinuo','Ámbar (s)','G + A + R (s)')):
        ax.set_ylabel(label)
        ax.grid(alpha=.2)
        for request in day.requests:
            ax.axvline(request.transition_start_s,color='#6d28d9',linestyle='--',alpha=.5)
            if request.transition_end_s > request.transition_start_s:
                ax.axvspan(request.transition_start_s,request.transition_end_s,color='#c4b5fd',alpha=.2)
    axes[0].legend(ncol=6,loc='upper right')
    axes[0].set_title('Duraciones y posición de fase separadas · '+('; '.join(r.status for r in day.requests) or 'NOMINAL'))
    axes[3].set_ylim(day.amber_s-1,day.amber_s+1)
    axes[4].set_ylim(day.cycle_s-1,day.cycle_s+1)
    axes[-1].set_xlim(left,right)
    axes[-1].xaxis.set_major_formatter(FuncFormatter(lambda value,_:day.timestamp(value)[11:19]))
    axes[-1].set_xlabel('Hora local de simulación')
    fig.tight_layout()
    fig.savefig(save_path,dpi=160,bbox_inches='tight')
    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_transition(transition: TransitionResult, base_green_s: List[float],
                    save_path: str = "transition.png",
                    max_change_fraction: float = 0.20, show: bool = True,
                    intersection_ids=None):
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    cycle, yellow = transition.cycle_s, transition.yellow_s
    count = transition.cycles_used
    x = list(range(count + 2))
    for i, base_green in enumerate(base_green_s):
        label = intersection_ids[i] if intersection_ids else f"S{i+1}"
        base_red = cycle - base_green - yellow
        final_green = transition.final_green_s[i] if transition.final_green_s else base_green
        greens = [base_green] + [row[i] for row in transition.green_history] + [final_green]
        reds = [base_red] + [row[i] for row in transition.red_history] + [cycle-yellow-final_green]
        line, = axes[0].plot(x, greens, marker="o", label=label)
        color = line.get_color()
        axes[1].plot(x, reds, marker="o", color=color)
        axes[2].plot(x, [g + yellow + r for g, r in zip(greens, reds)], marker="o", color=color)
    for ax, label in zip(axes, ("Verde (s)", "Rojo (s)", "Duración del ciclo físico (s)")):
        ax.set_ylabel(label)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(alpha=0.25)
        if count:
            ax.axvspan(0.5, count + 0.5, color="#c4b5fd", alpha=0.45)
    axes[2].axhline(cycle, color="#5b21b6", linestyle="--", linewidth=1)
    axes[2].set_ylim(cycle - max(1, cycle * 0.05), cycle + max(1, cycle * 0.05))
    axes[2].set_xticks(x, ["Base"] + [str(k) for k in range(1, count + 1)] + ["Bajada"])
    axes[2].set_xlabel("Ciclo de transición (Base y Bajada muestran los planes estables)")
    axes[0].set_title(f"Rampa de reparto: {count} ciclos · límite respecto a la base ±{max_change_fraction:.2%}\n"
                      f"Δrojo = −Δverde · amarillo = {yellow:g} s · ciclo físico = {cycle:g} s")
    axes[0].legend(ncol=3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=160)
    if show:
        plt.show()
    else:
        plt.close(fig)
