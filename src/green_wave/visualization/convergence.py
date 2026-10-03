from xml.sax.saxutils import escape

from green_wave.models.transition import TransitionResult


_PALETTE = ("#1261a0", "#8e44ad", "#c76711", "#147d4f", "#c23b65", "#555d7a")


def render_convergence_svg(result: TransitionResult) -> str:
    """Plot selected fitness values against physical application time."""
    ids = tuple(result.final_fitness)
    left, right, top, bottom = 65, 30, 45, 65
    width, height = 850, 360
    plot_width = width - left - right
    plot_height = height - top - bottom
    duration = max(1, result.ended_at_s - result.started_at_s)

    def x(time_s: int) -> float:
        return left + (time_s - result.started_at_s) * plot_width / duration

    def y(score: float) -> float:
        return top + (1 - score) * plot_height

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" role="img" aria-label="Convergencia de fitness">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             '<text x="20" y="25" font-family="sans-serif" font-size="17">Fitness por intersección</text>',
             f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#555"/>',
             f'<line x1="{left}" y1="{top + plot_height}" x2="{width - right}" '
             f'y2="{top + plot_height}" stroke="#555"/>',
             f'<text x="8" y="{top + 4}" font-family="sans-serif" font-size="11">1.0</text>',
             f'<text x="8" y="{top + plot_height + 4}" font-family="sans-serif" font-size="11">0.0</text>',
             f'<text x="{left}" y="{height - 37}" font-family="sans-serif" font-size="11">'
             f'{result.started_at_s} s</text>',
             f'<text x="{width - right - 50}" y="{height - 37}" font-family="sans-serif" font-size="11">'
             f'{result.ended_at_s} s</text>']
    for index, intersection_id in enumerate(ids):
        color = _PALETTE[index % len(_PALETTE)]
        steps = [step for step in result.steps if step.intersection_id == intersection_id]
        if steps:
            points = [(result.started_at_s, steps[0].previous_fitness)]
            points.extend((step.applied_at_s, step.next_fitness) for step in steps)
        else:
            points = [(result.started_at_s, result.final_fitness[intersection_id])]
        coordinates = " ".join(f"{x(time_s):.2f},{y(value):.2f}" for time_s, value in points)
        label = escape(intersection_id)
        parts.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" '
                     f'stroke-width="2"><title>{label}</title></polyline>')
        parts.append(f'<text x="{left + index * 105}" y="{height - 12}" '
                     f'font-family="sans-serif" font-size="11" fill="{color}">{label}</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
