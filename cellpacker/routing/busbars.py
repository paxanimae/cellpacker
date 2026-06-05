"""
cellpacker.routing.busbars
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parallel busbar rails and series jumpers.

Parallel busbars
    Within each series group, connect all + terminals together and all −
    terminals together.  The two groups are kept separate and placed at
    their respective terminal Z heights:

      ``_Busbars_Plus``  – positive-terminal rails at ``plus_busbar_z``
      ``_Busbars_Minus`` – negative-terminal rails at ``minus_busbar_z``

Series jumpers
    Connect the − rail of series group S to the + rail of group S+1.
    Each jumper runs from ``plus_busbar_z`` (the + endpoint) down to
    ``minus_busbar_z`` (the − endpoint), giving a physically correct
    diagonal rather than a flat offset wire.  Three styles:

    ``paired``  – one jumper per P-cell pair across the two groups.
    ``rail``    – single jumper between nearest endpoints of the two rails.
    ``single``  – one jumper from any terminal of group S to any of S+1.
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


def _at_z(pt: App.Vector, z: float) -> App.Vector:
    """Return a copy of *pt* with Z replaced by *z* (not added — absolute)."""
    return App.Vector(pt.x, pt.y, z)


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


def _try_add(parent, child) -> None:
    try:
        parent.addObject(child)
    except Exception:
        pass


# ── Parallel busbars ──────────────────────────────────────────────────────

def draw_parallel_busbars(
    doc,
    selected_by_series: dict[int, list[dict]],
    terminal_lookup: dict,
    parent_group,
    root_name: str,
    cfg: dict,
) -> None:
    """
    Connect like-polarity terminals within every series group.

    Creates two sub-groups under *parent_group*:
      ``<root>_Busbars_Plus``  at ``plus_busbar_z``
      ``<root>_Busbars_Minus`` at ``minus_busbar_z``
    """
    plus_z  = cfg.get("plus_busbar_z",  cfg.get("cell_height", 70.0))
    minus_z = cfg.get("minus_busbar_z", 0.0)

    plus_color  = cfg.get("plus_busbar_color",  (0.85, 0.10, 0.10))
    minus_color = cfg.get("minus_busbar_color", (0.10, 0.10, 0.85))

    grp_plus  = make_or_get_group(doc, root_name + "_Busbars_Plus")
    grp_minus = make_or_get_group(doc, root_name + "_Busbars_Minus")
    _try_add(parent_group, grp_plus)
    _try_add(parent_group, grp_minus)

    total_s = max(selected_by_series.keys()) if selected_by_series else 1

    for s, row in selected_by_series.items():
        if len(row) < 2:
            continue
        if cfg["colorize_series"]:
            series_color = get_series_color(s, total_s)
        else:
            series_color = None   # fall back to layer colour below

        c_plus  = series_color if series_color else plus_color
        c_minus = series_color if series_color else minus_color

        plus_pts  = [_at_z(terminal_lookup[(c["series"], c["parallel"])]["plus"],  plus_z)  for c in row]
        minus_pts = [_at_z(terminal_lookup[(c["series"], c["parallel"])]["minus"], minus_z) for c in row]

        _busbar_path(doc, plus_pts,  f"BUS_PLUS_S{s:02d}",  grp_plus,  cfg, c_plus)
        _busbar_path(doc, minus_pts, f"BUS_MINUS_S{s:02d}", grp_minus, cfg, c_minus)


# ── Series jumpers ────────────────────────────────────────────────────────

def draw_series_jumpers(
    doc,
    selected_by_series: dict[int, list[dict]],
    terminal_lookup: dict,
    parent_group,
    root_name: str,
    cfg: dict,
) -> None:
    """
    Connect consecutive series groups.

    Each jumper runs from the + rail of group S (at ``plus_busbar_z``) to
    the − rail of group S+1 (at ``minus_busbar_z``), matching the physical
    path a busbar takes between the two terminal faces of the cells.
    """
    plus_z  = cfg.get("plus_busbar_z",  cfg.get("cell_height", 70.0))
    minus_z = cfg.get("minus_busbar_z", 0.0)

    grp = make_or_get_group(doc, root_name + "_Busbars_Series")
    _try_add(parent_group, grp)

    style   = cfg.get("series_jumper_style", "paired")
    total_s = max(selected_by_series.keys()) if selected_by_series else 1

    sorted_series = sorted(selected_by_series.keys())

    for i, s in enumerate(sorted_series[:-1]):
        s_next = sorted_series[i + 1]
        row_a  = selected_by_series[s]
        row_b  = selected_by_series[s_next]

        # + side of S (at plus_z) → − side of S+1 (at minus_z)
        plus_pts_a  = [_at_z(terminal_lookup[(c["series"], c["parallel"])]["plus"],  plus_z)  for c in row_a]
        minus_pts_b = [_at_z(terminal_lookup[(c["series"], c["parallel"])]["minus"], minus_z) for c in row_b]

        color = get_series_color(s, total_s) if cfg["colorize_series"] else (0.20, 0.20, 0.20)
        label_base = f"BUS_SER_S{s:02d}_S{s_next:02d}"

        if style == "paired":
            n = min(len(plus_pts_a), len(minus_pts_b))
            for j in range(n):
                _busbar_path(doc, [plus_pts_a[j], minus_pts_b[j]],
                             f"{label_base}_P{j+1:02d}", grp, cfg, color)

        elif style == "rail":
            a, b = _nearest_pair(plus_pts_a, minus_pts_b)
            if a and b:
                _busbar_path(doc, [a, b], label_base, grp, cfg, color)

        else:  # "single" / legacy
            if plus_pts_a and minus_pts_b:
                _busbar_path(doc, [plus_pts_a[0], minus_pts_b[-1]],
                             label_base, grp, cfg, color)
