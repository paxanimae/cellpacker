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


def _spanning_edges(
    pts: list[App.Vector],
    pitch_x: float,
) -> list[tuple[App.Vector, App.Vector]]:
    """Return MST edges connecting *pts* via hex adjacency.

    Draws strips along actual cell-to-cell connections so within-group
    busbars never cut across cells of other groups.
    Falls back to a nearest-neighbour chain when no adjacency is found
    (degenerate / very small group).
    """
    n = len(pts)
    if n <= 1:
        return []

    threshold_sq = (pitch_x * 1.05) ** 2

    edges: list[tuple[float, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            dx = pts[i].x - pts[j].x
            dy = pts[i].y - pts[j].y
            d_sq = dx * dx + dy * dy
            if d_sq <= threshold_sq:
                edges.append((d_sq, i, j))

    if not edges:
        # No hex-adjacent pairs: nearest-neighbour fallback
        remaining = list(range(n))
        chain = [remaining.pop(0)]
        while remaining:
            last = chain[-1]
            nearest = min(
                remaining,
                key=lambda j: (pts[last].x - pts[j].x) ** 2 + (pts[last].y - pts[j].y) ** 2,
            )
            chain.append(nearest)
            remaining.remove(nearest)
        return [(pts[chain[k]], pts[chain[k + 1]]) for k in range(len(chain) - 1)]

    # Kruskal's MST
    edges.sort()
    parent = list(range(n))

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    result = []
    for _, i, j in edges:
        pi, pj = _find(i), _find(j)
        if pi != pj:
            parent[pi] = pj
            result.append((pts[i], pts[j]))
        if len(result) == n - 1:
            break

    return result


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


def _inter_group_edges(
    pts_a: list[App.Vector],
    pts_b: list[App.Vector],
    pitch_x: float,
    p_rating: int = 1,
) -> list[tuple[App.Vector, App.Vector]]:
    """Return bridge strip endpoints between groups A and B.

    Uses greedy 1-to-1 nearest-neighbour matching so each cell appears
    in at most one bridge strip.  Sorting by distance naturally prefers
    hex-adjacent pairs (shortest hops first) without crossing longer gaps.

    With p_rating=N, N matched pairs share one strip drawn between the
    centroid of the A-side cells and the centroid of the B-side cells.

    Returns one (pt_a, pt_b) pair per strip — always exactly
    ``ceil(min(len(pts_a), len(pts_b)) / p_rating)`` strips.
    """
    if not pts_a or not pts_b:
        return []

    # All cross-group distances, sorted nearest-first.
    all_pairs: list[tuple[float, int, int]] = []
    for i, pa in enumerate(pts_a):
        for j, pb in enumerate(pts_b):
            dx, dy = pa.x - pb.x, pa.y - pb.y
            all_pairs.append((dx * dx + dy * dy, i, j))
    all_pairs.sort()

    # Greedy 1-to-1 match: each cell in A and B used at most once.
    used_a: set[int] = set()
    used_b: set[int] = set()
    matched: list[tuple[App.Vector, App.Vector]] = []

    for _, i, j in all_pairs:
        if i in used_a or j in used_b:
            continue
        matched.append((pts_a[i], pts_b[j]))
        used_a.add(i)
        used_b.add(j)
        if len(used_a) == len(pts_a) or len(used_b) == len(pts_b):
            break

    # Group matched pairs by p_rating → one strip per group (centroid-to-centroid).
    p = max(1, p_rating)

    def _centroid(vecs: list[App.Vector]) -> App.Vector:
        n = len(vecs)
        return App.Vector(
            sum(v.x for v in vecs) / n,
            sum(v.y for v in vecs) / n,
            sum(v.z for v in vecs) / n,
        )

    result: list[tuple[App.Vector, App.Vector]] = []
    for start in range(0, len(matched), p):
        chunk = matched[start:start + p]
        result.append((
            _centroid([pa for pa, _ in chunk]),
            _centroid([pb for _, pb in chunk]),
        ))

    return result


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

    pitch_x = cfg.get("cell_diameter", 18.4) + cfg.get("clearance", 0.8)

    for s, row in selected_by_series.items():
        if len(row) < 2:
            continue

        top_pts = [_cell_center(terminal_lookup, c["series"], c["parallel"],
                                sketch_normal, top_z) for c in row]
        bot_pts = [_cell_center(terminal_lookup, c["series"], c["parallel"],
                                sketch_normal, bottom_z) for c in row]

        # Draw one strip per adjacent cell pair (MST) so the busbar follows
        # the actual cluster shape and never crosses cells of other groups.
        for idx, (p1, p2) in enumerate(_spanning_edges(top_pts, pitch_x), start=1):
            _busbar_segment(doc, p1, p2, f"BB_S{s:02d}_{idx:02d}", grp_top,
                            cfg, color_top, sketch_normal)
        for idx, (p1, p2) in enumerate(_spanning_edges(bot_pts, pitch_x), start=1):
            _busbar_segment(doc, p1, p2, f"BB_S{s:02d}_{idx:02d}", grp_bottom,
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

        pitch_x = cfg.get("cell_diameter", 18.4) + cfg.get("clearance", 0.8)

        pts_a = [_cell_center(terminal_lookup, c["series"], c["parallel"],
                              sketch_normal, bridge_z) for c in row_a]
        pts_b = [_cell_center(terminal_lookup, c["series"], c["parallel"],
                              sketch_normal, bridge_z) for c in row_b]

        label = f"BB_S{s:02d}_S{s_next:02d}"
        p_rating = max(1, cfg.get("busbar_p_rating", 1))
        for idx, (pa, pb) in enumerate(
            _inter_group_edges(pts_a, pts_b, pitch_x, p_rating), start=1
        ):
            _busbar_segment(doc, pa, pb, f"{label}_{idx:02d}",
                            grp, cfg, color, sketch_normal)
