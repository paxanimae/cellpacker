"""
cellpacker.routing.busbars
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parallel busbar rails and series jumpers.

Parallel busbars
    Within each series group, connect all + terminals together and all −
    terminals together with a polyline or solid strip.

Series jumpers
    Connect the − rail of series group S to the + rail of group S+1
    (or vice-versa, depending on polarity convention).  Three styles:

    ``paired``  – connect each P-cell terminal to the matching P-cell in
                  the next group (one jumper per P cell).
    ``rail``    – one jumper between the nearest endpoints of the two rails.
    ``single``  – one jumper from any terminal of group S to any terminal
                  of group S+1 (legacy).
"""

from __future__ import annotations
import FreeCAD as App

from cellpacker.drawing.cells import make_or_get_group
from cellpacker.drawing.colors import get_series_color
from cellpacker.drawing.primitives import draw_polyline, draw_busbar_strip


# ── Helpers ────────────────────────────────────────────────────────────────

def _busbar_path(
    doc,
    points: list[App.Vector],
    label: str,
    group,
    cfg: dict,
    color: tuple,
) -> list:
    """Draw either a solid strip sequence or a polyline, per *cfg*."""
    if len(points) < 2:
        return []
    created = []
    if cfg["draw_busbar_solids"]:
        for i in range(len(points) - 1):
            seg = draw_busbar_strip(
                doc, points[i], points[i + 1],
                cfg["busbar_width"], cfg["busbar_thickness"],
                f"{label}_{i+1:02d}", group, color=color,
            )
            if seg is not None:
                created.append(seg)
    else:
        created.append(draw_polyline(doc, points, label, group, color=color))
    return created


def _with_z(pt: App.Vector, z_off: float) -> App.Vector:
    return App.Vector(pt.x, pt.y, pt.z + z_off)


def _nearest_pair(
    pts_a: list[App.Vector],
    pts_b: list[App.Vector],
) -> tuple[App.Vector | None, App.Vector | None]:
    best_dist = None
    best_a = best_b = None
    for a in pts_a:
        for b in pts_b:
            d = a.distanceToPoint(b)
            if best_dist is None or d < best_dist:
                best_dist, best_a, best_b = d, a, b
    return best_a, best_b


# ── Parallel busbars ──────────────────────────────────────────────────────

def draw_parallel_busbars(
    doc,
    selected_by_series: dict[int, list[dict]],
    terminal_lookup: dict,
    parent_group,
    root_name: str,
    cfg: dict,
) -> None:
    """Connect like-polarity terminals within every series group."""
    grp = make_or_get_group(doc, root_name + "_Busbars_Parallel")
    try:
        parent_group.addObject(grp)
    except Exception:
        pass

    total_s = max(selected_by_series.keys()) if selected_by_series else 1

    for s, row in selected_by_series.items():
        if len(row) < 2:
            continue
        color = (
            get_series_color(s, total_s)
            if cfg["colorize_series"]
            else (0.2, 0.2, 0.8)
        )
        plus_pts  = [terminal_lookup[(c["series"], c["parallel"])]["plus"]  for c in row]
        minus_pts = [terminal_lookup[(c["series"], c["parallel"])]["minus"] for c in row]

        _busbar_path(doc, plus_pts,  f"BUS_PAR_PLUS_S{s:02d}",  grp, cfg, color)
        _busbar_path(doc, minus_pts, f"BUS_PAR_MINUS_S{s:02d}", grp, cfg, color)


# ── Series jumpers ────────────────────────────────────────────────────────

def draw_series_jumpers(
    doc,
    selected_by_series: dict[int, list[dict]],
    terminal_lookup: dict,
    parent_group,
    root_name: str,
    cfg: dict,
) -> None:
    """Connect consecutive series groups with the configured jumper style."""
    grp = make_or_get_group(doc, root_name + "_Busbars_Series")
    try:
        parent_group.addObject(grp)
    except Exception:
        pass

    style = cfg.get("series_jumper_style", "paired")
    alternate = cfg.get("alternate_series_jumper_layers", True)
    top_z    = cfg.get("top_layer_z",    0.5)
    bottom_z = cfg.get("bottom_layer_z", -0.5)
    top_col  = cfg.get("top_layer_color",    (0.10, 0.10, 0.10))
    bot_col  = cfg.get("bottom_layer_color", (0.45, 0.45, 0.45))

    sorted_series = sorted(selected_by_series.keys())

    for i, s in enumerate(sorted_series[:-1]):
        s_next = sorted_series[i + 1]
        row_a  = selected_by_series[s]
        row_b  = selected_by_series[s_next]

        # + side of s connects to − side of s_next (series convention)
        plus_pts_a  = [terminal_lookup[(c["series"], c["parallel"])]["plus"]  for c in row_a]
        minus_pts_b = [terminal_lookup[(c["series"], c["parallel"])]["minus"] for c in row_b]

        z_off = top_z if (i % 2 == 0) else bottom_z
        color = top_col if (i % 2 == 0) else bot_col
        if not alternate:
            z_off = top_z
            color = top_col

        label_base = f"BUS_SER_S{s:02d}_S{s_next:02d}"

        if style == "paired":
            n = min(len(plus_pts_a), len(minus_pts_b))
            for j in range(n):
                a = _with_z(plus_pts_a[j],  z_off)
                b = _with_z(minus_pts_b[j], z_off)
                _busbar_path(doc, [a, b], f"{label_base}_P{j+1:02d}", grp, cfg, color)

        elif style == "rail":
            a, b = _nearest_pair(
                [_with_z(p, z_off) for p in plus_pts_a],
                [_with_z(p, z_off) for p in minus_pts_b],
            )
            if a and b:
                _busbar_path(doc, [a, b], label_base, grp, cfg, color)

        else:  # "single" / legacy
            if plus_pts_a and minus_pts_b:
                a = _with_z(plus_pts_a[0],  z_off)
                b = _with_z(minus_pts_b[-1], z_off)
                _busbar_path(doc, [a, b], label_base, grp, cfg, color)
