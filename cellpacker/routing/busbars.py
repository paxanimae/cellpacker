"""
cellpacker.routing.busbars
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Busbar drawing for a battery pack.

A busbar is a busbar — there is no "parallel busbar" or "series busbar".
The distinction is purely topological.  Physically, every strip lives on
one face of the pack and connects whatever terminals are exposed there.

Cells alternate orientation by series group:
  Odd  groups (S01, S03, …): + terminal at top face, − at bottom face.
  Even groups (S02, S04, …): − terminal at top face, + terminal at bottom face.

Face routing:
  Top face:    odd-group  within-group (+) rails
               even-group within-group (−) rails
               S_odd → S_even   series bridges  (both share the top face)
  Bottom face: odd-group  within-group (−) rails
               even-group within-group (+) rails
               S_even → S_odd   series bridges  (both share the bottom face)

Connection count is driven by the busbar p_rating from the catalog:
  p_rating = 1 → one strip per cell pair
  p_rating = N → one strip per N cell pairs (fewer, wider strips)
"""

from __future__ import annotations
import math
import FreeCAD as App

from cellpacker.drawing.cells import make_or_get_group
from cellpacker.drawing.primitives import draw_busbar_face, draw_busbar_strip


# ── Internal helpers ───────────────────────────────────────────────────────

def _along_normal(pt: App.Vector, normal: App.Vector, dist: float) -> App.Vector:
    """Offset *pt* by *dist* mm along *normal*."""
    return App.Vector(
        pt.x + normal.x * dist,
        pt.y + normal.y * dist,
        pt.z + normal.z * dist,
    )


def _cell_center(tl: dict, s: int, p: int, normal: App.Vector, z: float) -> App.Vector:
    """Return the cell-center position on face Z.

    The terminal_lookup stores plus/minus positions offset by polarity_offset
    from the actual cell centre.  The average of plus and minus cancels that
    offset, giving the true XY centre.  We then shift along the sketch normal
    to the requested face height.
    """
    plus  = tl[(s, p)]["plus"]
    minus = tl[(s, p)]["minus"]
    cx = (plus.x + minus.x) / 2.0
    cy = (plus.y + minus.y) / 2.0
    cz = (plus.z + minus.z) / 2.0
    return _along_normal(App.Vector(cx, cy, cz), normal, z)


def _try_add(parent, child) -> None:
    try:
        parent.addObject(child)
    except Exception:
        pass


def _busbar_segment(
    doc,
    p1: App.Vector,
    p2: App.Vector,
    label: str,
    group,
    cfg: dict,
    color: tuple,
    sketch_normal: App.Vector,
) -> object | None:
    """Draw one busbar strip segment between *p1* and *p2*."""
    width = cfg.get("busbar_width", 8.0)
    if cfg.get("draw_busbar_solids", False):
        return draw_busbar_strip(
            doc, p1, p2, width, cfg.get("busbar_thickness", 0.2),
            label, group, color=color,
        )
    else:
        return draw_busbar_face(
            doc, p1, p2, width, label, group, color=color,
            normal=sketch_normal,
        )


def _draw_bridges(
    doc,
    pts_a: list[App.Vector],
    pts_b: list[App.Vector],
    label: str,
    group,
    cfg: dict,
    color: tuple,
    sketch_normal: App.Vector,
) -> None:
    """Draw series bridge strips from each cell in group A to its partner in B.

    Respects p_rating: with p_rating=N, N cell pairs share one strip
    (the strip runs from the centroid of the N pts_a cells to the
    centroid of the N pts_b cells).
    """
    n = min(len(pts_a), len(pts_b))
    if n == 0:
        return
    p = max(1, cfg.get("busbar_p_rating", 1))
    chunks = math.ceil(n / p)
    for chunk in range(chunks):
        lo = chunk * p
        hi = min(lo + p, n)
        # Representative points: first and last in the chunk give the two
        # endpoints of the bridge strip.  For p=1 this is just one-to-one.
        a_start = pts_a[lo]
        a_end   = pts_a[hi - 1]
        b_start = pts_b[lo]
        b_end   = pts_b[hi - 1]
        # Midpoints of the A-cluster and B-cluster define the strip axis.
        mid_a = App.Vector(
            (a_start.x + a_end.x) / 2,
            (a_start.y + a_end.y) / 2,
            (a_start.z + a_end.z) / 2,
        )
        mid_b = App.Vector(
            (b_start.x + b_end.x) / 2,
            (b_start.y + b_end.y) / 2,
            (b_start.z + b_end.z) / 2,
        )
        _busbar_segment(
            doc, mid_a, mid_b,
            f"{label}_{chunk + 1:02d}", group, cfg, color, sketch_normal,
        )


# ── Public drawing functions ───────────────────────────────────────────────

def draw_parallel_busbars(
    doc,
    selected_by_series: dict[int, list[dict]],
    terminal_lookup: dict,
    parent_group,
    root_name: str,
    cfg: dict,
    sketch_normal: App.Vector,
) -> None:
    """Draw within-group face rails for every series group.

    Each group's terminals are split between the top and bottom face
    according to the group's cell orientation parity.  A busbar rail
    is drawn on each face connecting all the group's terminals on that face.
    """
    top_z    = cfg.get("layer_z_top",    0.0)
    bottom_z = cfg.get("layer_z_bottom", 0.0)

    color_top    = cfg.get("busbar_color_top",    (0.90, 0.55, 0.10))
    color_bottom = cfg.get("busbar_color_bottom", (0.15, 0.45, 0.90))

    grp_top    = make_or_get_group(doc, root_name + "_Busbars_Top")
    grp_bottom = make_or_get_group(doc, root_name + "_Busbars_Bottom")
    _try_add(parent_group, grp_top)
    _try_add(parent_group, grp_bottom)

    for s, row in selected_by_series.items():
        if len(row) < 2:
            continue

        # Odd groups: + terminal at top face, − at bottom face.
        # Even groups: reversed.
        if s % 2 == 1:
            top_pol, bottom_pol = "plus",  "minus"
        else:
            top_pol, bottom_pol = "minus", "plus"

        top_pts = sorted(
            [_cell_center(terminal_lookup, c["series"], c["parallel"],
                          sketch_normal, top_z) for c in row],
            key=lambda p: p.x,
        )
        bot_pts = sorted(
            [_cell_center(terminal_lookup, c["series"], c["parallel"],
                          sketch_normal, bottom_z) for c in row],
            key=lambda p: p.x,
        )

        # One long strip spanning the full row — optimise for length.
        if len(top_pts) >= 2:
            _busbar_segment(doc, top_pts[0], top_pts[-1],
                            f"BB_S{s:02d}", grp_top,
                            cfg, color_top, sketch_normal)
        if len(bot_pts) >= 2:
            _busbar_segment(doc, bot_pts[0], bot_pts[-1],
                            f"BB_S{s:02d}", grp_bottom,
                            cfg, color_bottom, sketch_normal)


def draw_series_busbars(
    doc,
    selected_by_series: dict[int, list[dict]],
    terminal_lookup: dict,
    parent_group,
    root_name: str,
    cfg: dict,
    sketch_normal: App.Vector,
) -> None:
    """Draw between-group bridge strips connecting adjacent series groups.

    The bridge always lives on the face that both groups share:
      Odd S → even S+1:   both expose the connecting terminals on the TOP face.
      Even S → odd S+1:   both expose the connecting terminals on the BOTTOM face.
    """
    top_z    = cfg.get("layer_z_top",    0.0)
    bottom_z = cfg.get("layer_z_bottom", 0.0)

    color_top    = cfg.get("busbar_color_top",    (0.90, 0.55, 0.10))
    color_bottom = cfg.get("busbar_color_bottom", (0.15, 0.45, 0.90))

    grp_top    = make_or_get_group(doc, root_name + "_Busbars_Top")
    grp_bottom = make_or_get_group(doc, root_name + "_Busbars_Bottom")
    _try_add(parent_group, grp_top)
    _try_add(parent_group, grp_bottom)

    sorted_series = sorted(selected_by_series.keys())

    for i, s in enumerate(sorted_series[:-1]):
        s_next = sorted_series[i + 1]
        row_a  = selected_by_series[s]
        row_b  = selected_by_series[s_next]

        # Odd S: + at top → top-face bridge.
        # Even S: + at bottom → bottom-face bridge.
        if s % 2 == 1:
            bridge_z = top_z
            grp      = grp_top
            color    = color_top
            pol_a, pol_b = "plus", "minus"   # S_odd(+top) → S_next(−top)
        else:
            bridge_z = bottom_z
            grp      = grp_bottom
            color    = color_bottom
            pol_a, pol_b = "plus", "minus"   # S_even(+bot) → S_next(−bot)

        pts_a = sorted(
            [_cell_center(terminal_lookup, c["series"], c["parallel"],
                          sketch_normal, bridge_z) for c in row_a],
            key=lambda p: p.x,
        )
        pts_b = sorted(
            [_cell_center(terminal_lookup, c["series"], c["parallel"],
                          sketch_normal, bridge_z) for c in row_b],
            key=lambda p: p.x,
        )

        _draw_bridges(
            doc, pts_a, pts_b,
            f"BB_S{s:02d}_S{s_next:02d}",
            grp, cfg, color, sketch_normal,
        )
