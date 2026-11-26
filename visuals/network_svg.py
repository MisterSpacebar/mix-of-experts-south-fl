"""Dependency-free directed node-link SVGs for *existing* learned FCM edges.

A graph is a filtered view of one station-level fitted matrix. Neither
within-category nor within-subcategory views are separately fitted experts.
Retain ALL original edges in CSV; display threshold applies to SVG ONLY.
"""
from __future__ import annotations

from html import escape
from math import cos, sin, pi, hypot, isfinite

from .hierarchy import classify

CATEGORY_FILL = {
    "hydrology": "#e7f1fc",
    "water_quality": "#e3f5f1",
    "oceanography": "#edf0ff",
    "ecology": "#edf7e5",
    "socioeconomic": "#fff1e0",
    "unclassified": "#f2f3f5",
}
POSITIVE = "#256f9c"
NEGATIVE = "#b26750"
STROKE = "#46677b"
VIEW_WARNING = (
    "Descriptive projection of one trained station FCM; "
    "not an independently fitted category/subcategory model or causal graph."
)


def _display(label):
    return str(label).replace("_", " ")


def _weight(edge):
    try:
        value = float(edge["weight"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("FCM edge missing a numeric weight") from exc
    if not isfinite(value) or value < -1.000001 or value > 1.000001:
        raise ValueError("FCM edge weight must be finite and in [-1,1]")
    return value


def network_svg(concepts, edges, *, title, subtitle="", min_abs=0.08,
                max_edges=36, view_warning=VIEW_WARNING):
    """Return a standalone 1040x720 SVG with genuine directed signed arrows.

    The incoming edges must belong to this concept subset. Self-memory
    is displayed separately with a loop and weight where available; all
    other arrows above threshold are selected by absolute weight.
    """
    nodes = list(concepts)
    if not nodes or len(set(nodes)) != len(nodes):
        raise ValueError("network requires one or more unique concept names")
    if len(nodes) > 24:
        raise ValueError("maximum 24 concepts per diagram; split into subcategories")
    if not 0 <= min_abs <= 1 or not 1 <= max_edges <= 120:
        raise ValueError("edge threshold or display cap out of range")
    allowed = set(nodes)
    normalized = []
    seen = set()
    for edge in edges:
        source, target = edge["source_concept"], edge["target_concept"]
        if source not in allowed or target not in allowed:
            raise ValueError("network edge references concept outside selected scope")
        pair = (source, target)
        if pair in seen:
            raise ValueError("duplicate directed source/target edge")
        seen.add(pair)
        normalized.append((source, target, _weight(edge)))
    self_memory = {source: w for source, target, w in normalized
                   if source == target}
    cross = [(source, target, w) for source, target, w in normalized
             if source != target and abs(w) >= min_abs]
    cross.sort(key=lambda e: (-abs(e[2]), e[0], e[1]))
    displayed = cross[:max_edges]
    omitted = len(cross) - len(displayed)
    n = len(nodes)
    center_x, center_y = 520.0, 330.0
    radius = 0 if n == 1 else (165 if n == 2 else (218 if n <= 6 else 252))
    # Stable concept positions, independent of which edges passed threshold.
    points = {}
    for i, name in enumerate(nodes):
        angle = -pi/2 + 2*pi*i/n if n != 2 else pi - pi*i
        points[name] = (center_x + radius*cos(angle),
                        center_y + radius*sin(angle))
    width, height = 1040, 720
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img"',
        f' aria-label="{escape(title, quote=True)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<defs>',
        f'<marker id="positive" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="{POSITIVE}"/></marker>',
        f'<marker id="negative" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="{NEGATIVE}"/></marker>',
        '</defs>',
        f'<text x="40" y="44" font-size="23" font-weight="bold" font-family="Arial,sans-serif" fill="#173d58">{escape(title)}</text>',
        f'<text x="40" y="70" font-size="13" font-family="Arial,sans-serif" fill="#506675">{escape(subtitle)}</text>',
        '<g fill="none" stroke-linecap="round">',
    ]
    # All arrows originate from the observed/source concept at day t, and
    # terminate at the target concept at day t+1.
    displayed_pairs = {(a,b) for a,b,_ in displayed}
    for source, target, weight in displayed:
        ax, ay = points[source]
        bx, by = points[target]
        dx, dy = bx-ax, by-ay
        distance = hypot(dx,dy)
        if distance < 1:
            continue
        ux,uy=dx/distance,dy/distance
        px,py=-uy,ux
        reciprocal = (target,source) in displayed_pairs
        curve = 58.0 if reciprocal else 14.0
        start = (ax + ux*62,ay + uy*62)
        end = (bx - ux*68,by - uy*68)
        cx = (start[0]+end[0])/2 + px*curve
        cy = (start[1]+end[1])/2 + py*curve
        color = POSITIVE if weight >= 0 else NEGATIVE
        marker = "positive" if weight >= 0 else "negative"
        thickness = 1.5 + 3.3*abs(weight)
        lines.append(
            f'<path d="M {start[0]:.1f},{start[1]:.1f} '
            f'Q {cx:.1f},{cy:.1f} {end[0]:.1f},{end[1]:.1f}" '
            f'stroke="{color}" stroke-width="{thickness:.2f}" '
            f'opacity=".86" marker-end="url(#{marker})"/>'
        )
        lx = (start[0]+2*cx+end[0])/4
        ly = (start[1]+2*cy+end[1])/4
        lines.append(f'<rect x="{lx-23:.1f}" y="{ly-12:.1f}" width="46" height="22" rx="7" fill="#ffffff" stroke="#e3eaf0"/>')
        lines.append(f'<text x="{lx:.1f}" y="{ly+3:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="{color}">{weight:+.2f}</text>')
    lines.append('</g>')
    for name in nodes:
        x,y=points[name]
        category,subcat=classify(name)
        color=CATEGORY_FILL.get(category,CATEGORY_FILL["unclassified"])
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="57" fill="{color}" stroke="{STROKE}" stroke-width="1.5"/>')
        label=_display(name)
        # Split longer labels into at most two lines, preserving readability.
        words=label.split()
        if len(label)>14 and len(words)>1:
            mid=(len(words)+1)//2
            text_lines=[" ".join(words[:mid])," ".join(words[mid:])]
        else:
            text_lines=[label]
        label_start = y-12 if len(text_lines)==1 else y-20
        for k,value in enumerate(text_lines):
            lines.append(f'<text x="{x:.1f}" y="{label_start+15*k:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" font-weight="bold" fill="#173e55">{escape(value)}</text>')
        lines.append(f'<text x="{x:.1f}" y="{y+18:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="9.5" fill="#556e7b">{escape(_display(category))}</text>')
        if name in self_memory:
            weight=self_memory[name]
            # An explicit small self-loop arrow above-right of the concept.
            x0,y0=x+42,y-36
            x1,y1=x+8,y-58
            col=POSITIVE if weight>=0 else NEGATIVE
            mark="positive" if weight>=0 else "negative"
            lines.append(
                f'<path d="M {x0:.1f},{y0:.1f} C {x+105:.1f},{y-99:.1f} '
                f'{x+20:.1f},{y-107:.1f} {x1:.1f},{y1:.1f}" '
                f'fill="none" stroke="{col}" stroke-width="1.7" '
                f'marker-end="url(#{mark})"/>')
            lines.append(f'<text x="{x+58:.1f}" y="{y-88:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="{col}">self {weight:+.2f}</text>')
    lines += [
        f'<rect x="40" y="607" width="20" height="4" rx="2" fill="{POSITIVE}"/>',
        '<text x="70" y="613" font-family="Arial,sans-serif" font-size="12" fill="#526778">Positive lag-one weight</text>',
        f'<rect x="290" y="607" width="20" height="4" rx="2" fill="{NEGATIVE}"/>',
        '<text x="320" y="613" font-family="Arial,sans-serif" font-size="12" fill="#526778">Negative lag-one weight</text>',
        f'<text x="40" y="643" font-family="Arial,sans-serif" font-size="12" fill="#5f7181">{len(displayed)} of {len(cross)} non-self edges shown at |weight| ≥ {min_abs:.2f}; {omitted} capped for readability.</text>',
        f'<text x="40" y="670" font-family="Arial,sans-serif" font-size="12" fill="#5f7181">{escape(view_warning)}</text>',
        '<text x="40" y="697" font-family="Arial,sans-serif" font-size="11" fill="#72838d">Edge direction: source today → target next day. Self arrows denote memory, not causality.</text>',
        '</svg>',
    ]
    return "\n".join(lines)
