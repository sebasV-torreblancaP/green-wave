from green_wave.simulation.trace import SignalTrace
from xml.sax.saxutils import escape

from green_wave.models.transition import TransitionResult


_COLORS = {"R": "#cf5656", "V": "#3aa775", "A": "#e6ad40"}


def render_text_timeline(trace: SignalTrace) -> str:
    first = trace.samples[0].time_s
    last = trace.samples[-1].time_s + 1
    states = "".join(sample.phase.value for sample in trace.samples)
    return f"{trace.intersection_id} [{first}, {last}): {states}"


def render_signal_svg(result: TransitionResult, origins_a: dict[str, int],
                      origins_b: dict[str, int]) -> str:
    """Render executed signal traces and applied-step markers as standalone SVG."""
    traces = result.traces
    if not traces:
        raise ValueError("no hay trazas para visualizar")
    start = result.started_at_s
    end = max(trace.samples[-1].time_s + 1 for trace in traces.values())
    scale = 3
    left = 215
    top = 65
    row_height = 43
    width = left + (end - start) * scale + 35
    height = top + len(traces) * row_height + 40
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" role="img" aria-label="Ciclos semafóricos">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             '<text x="16" y="25" font-family="sans-serif" font-size="17">Señales ejecutadas</text>',
             f'<text x="{left}" y="49" font-family="sans-serif" font-size="11">'
             f'Tiempo: {start} a {end} s; R rojo, V verde, A amarillo</text>']
    for index, (intersection_id, trace) in enumerate(traces.items()):
        if intersection_id not in origins_a or intersection_id not in origins_b:
            raise ValueError(f"faltan orígenes para {intersection_id}")
        y = top + index * row_height
        label = escape(intersection_id)
        parts.append(f'<text x="12" y="{y + 17}" font-family="sans-serif" font-size="12">'
                     f'{label} · A:{origins_a[intersection_id]} B:{origins_b[intersection_id]} s</text>')
        samples = trace.samples
        run_start = 0
        for sample_index in range(1, len(samples) + 1):
            if sample_index != len(samples) and samples[sample_index].phase == samples[run_start].phase:
                continue
            phase = samples[run_start].phase.value
            start_time = samples[run_start].time_s
            run_length = sample_index - run_start
            x = left + (start_time - start) * scale
            color = _COLORS[phase]
            parts.append(f'<rect x="{x}" y="{y}" width="{run_length * scale}" height="24" '
                         f'fill="{color}"><title>{label}: {phase} [{start_time}, {start_time + run_length}) s</title></rect>')
            run_start = sample_index
        for step in result.steps:
            if step.intersection_id == intersection_id:
                x = left + (step.applied_at_s - start) * scale
                parts.append(f'<line x1="{x}" y1="{y - 3}" x2="{x}" y2="{y + 28}" '
                             f'stroke="#20314b" stroke-width="2"><title>'
                             f'{label} T{step.local_cycle} en {step.applied_at_s} s</title></line>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
