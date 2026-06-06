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
        # Scale mm width to a visible pixel line width (1 mm ≈ 0.5 px at typical zoom)
        lw = max(1.0, cfg.get("busbar_width", 8.0) * 0.5)
        created.append(draw_polyline(doc, points, label, group, color=color, line_width=lw))
    return created


def _along_normal(pt: App.Vector, normal: App.Vector, distance: float) -> App.Vector:
    """Offset *pt* by *distance* mm along *normal* (sketch-plane perpendicular).

    Using the sketch normal rather than raw world-Z works correctly for
    sketches that are not in the world XY plane.
    """
    return App.Vector(
        pt.x + normal.x * distance,
        pt.y + normal.y * distance,
        pt.z + normal.z * distance,
    )


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
    sketch_normal: App.Vector,
) -> None:
    """
    Connect terminals within every series group on the correct face.

    Odd groups  (S01, S03, …): + terminal at top face, − at bottom face.
    Even groups (S02, S04, …): + terminal at bottom face, − at top face.

    Groups are placed in ``<root>_Busbars_Top`` and ``<root>_Busbars_Bottom``.
    """
    top_z    = cfg.get("layer_z_top",    0.0)
    bottom_z = cfg.get("layer_z_bottom", 0.0)

    color_top    = cfg.get("plus_busbar_color",  (0.85, 0.10, 0.10))
    color_bottom = cfg.get("minus_busbar_color", (0.10, 0.10, 0.85))

    grp_top    = make_or_get_group(doc, root_name + "_Busbars_Top")
    grp_bottom = make_or_get_group(doc, root_name + "_Busbars_Bottom")
    _try_add(parent_group, grp_top)
    _try_add(parent_group, grp_bottom)

    total_s = max(selected_by_series.keys()) if selected_by_series else 1

    for s, row in selected_by_series.items():
        if len(row) < 2:
            continue

        color = get_series_color(s, total_s) if cfg["colorize_series"] else None

        # Odd groups: + faces up (top face), − faces down (bottom face).
        # Even groups: reversed.
        if s % 2 == 1:
            top_pol, bottom_pol = "plus",  "minus"
            grp_top_use, grp_bot_use = grp_top, grp_bottom
            c_top, c_bot = color or color_top, color or color_bottom
        else:
            top_pol, bottom_pol = "minus", "plus"
            grp_top_use, grp_bot_use = grp_top, grp_bottom
            c_top, c_bot = color or color_bottom, color or color_top

        top_pts = sorted(
            [_along_normal(terminal_lookup[(c["series"], c["parallel"])][top_pol],
                           sketch_normal, top_z) for c in row],
            key=lambda p: p.x,
        )
        bot_pts = sorted(
            [_along_normal(terminal_lookup[(c["series"], c["parallel"])][bottom_pol],
                           sketch_normal, bottom_z) for c in row],
            key=lambda p: p.x,
        )

        _busbar_path(doc, top_pts, f"BUS_TOP_S{s:02d}",    grp_top_use, cfg, c_top)
        _busbar_path(doc, bot_pts, f"BUS_BOTTOM_S{s:02d}", grp_bot_use, cfg, c_bot)


# ── Series jumpers ────────────────────────────────────────────────────────

def draw_series_jumpers(
    doc,
    selected_by_series: dict[int, list[dict]],
    terminal_lookup: dict,
    parent_group,
    root_name: str,
    cfg: dict,
    sketch_normal: App.Vector,
) -> None:
    """
    Connect consecutive series groups, staying on the correct face.

    Odd group S → even group S+1: both share the TOP face
      (S's + terminal is at top; S+1's − terminal is also at top).
    Even group S → odd group S+1: both share the BOTTOM face.

    Series jumpers are placed in the same top/bottom group as the
    parallel busbars they connect to.
    """
    top_z    = cfg.get("layer_z_top",    0.0)
    bottom_z = cfg.get("layer_z_bottom", 0.0)

    grp_top    = make_or_get_group(doc, root_name + "_Busbars_Top")
    grp_bottom = make_or_get_group(doc, root_name + "_Busbars_Bottom")
    _try_add(parent_group, grp_top)
    _try_add(parent_group, grp_bottom)

    style   = cfg.get("series_jumper_style", "paired")
    total_s = max(selected_by_series.keys()) if selected_by_series else 1

    sorted_series = sorted(selected_by_series.keys())

    for i, s in enumerate(sorted_series[:-1]):
        s_next = sorted_series[i + 1]
        row_a  = selected_by_series[s]
        row_b  = selected_by_series[s_next]

        # Odd S: + at top, next group's − also at top → top face jumper.
        if s % 2 == 1:
            jumper_z = top_z
            grp      = grp_top
            pol_a, pol_b = "plus", "minus"
        else:
            jumper_z = bottom_z
            grp      = grp_bottom
            pol_a, pol_b = "plus", "minus"

        pts_a = [_along_normal(terminal_lookup[(c["series"], c["parallel"])][pol_a],
                               sketch_normal, jumper_z) for c in row_a]
        pts_b = [_along_normal(terminal_lookup[(c["series"], c["parallel"])][pol_b],
                               sketch_normal, jumper_z) for c in row_b]

        color      = get_series_color(s, total_s) if cfg["colorize_series"] else (0.20, 0.20, 0.20)
        label_base = f"BUS_SER_S{s:02d}_S{s_next:02d}"

        if style == "paired":
            a_sorted = sorted(pts_a, key=lambda p: p.x)
            b_sorted = sorted(pts_b, key=lambda p: p.x)
            n = min(len(a_sorted), len(b_sorted))
            for j in range(n):
                _busbar_path(doc, [a_sorted[j], b_sorted[j]],
                             f"{label_base}_P{j+1:02d}", grp, cfg, color)

        elif style == "rail":
            a, b = _nearest_pair(pts_a, pts_b)
            if a and b:
                _busbar_path(doc, [a, b], label_base, grp, cfg, color)

        else:  # "single" / legacy
            if pts_a and pts_b:
                _busbar_path(doc, [pts_a[0], pts_b[-1]],
                             label_base, grp, cfg, color)
