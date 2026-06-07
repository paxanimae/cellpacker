"""
cellpacker.layout.serpentine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Serpentine (boustrophedon) layout algorithm.

All candidate cells are sorted into rows, then traversed in alternating
direction to form a single 1-D path.  Series groups are assigned by taking
P consecutive cells from this path.

This guarantees by construction:
  - Connected groups          consecutive cells in a row are always hex-adjacent
  - Short bridges             consecutive groups share a row boundary
  - No busbar crossings       path order == wiring order
  - Predictable terminals     start corner  == PACK−,  end ≈ PACK+
"""

from __future__ import annotations
import math

from cellpacker.layout.rows import cluster_rows


# 8-position compass (same definition as graph.py — kept local to avoid circular import)
CORNERS: dict[str, tuple[int, int]] = {
    "top-left":     (-1,  1),
    "top":          ( 0,  1),
    "top-right":    ( 1,  1),
    "right":        ( 1,  0),
    "bottom-right": ( 1, -1),
    "bottom":       ( 0, -1),
    "bottom-left":  (-1, -1),
    "left":         (-1,  0),
}

FAILURE_MESSAGES: dict[str, str] = {
    "not_enough_candidates": (
        "Not enough candidate cells for the requested S×P count.\n"
        "Try a smaller pack, a larger sketch, or a smaller cell diameter."
    ),
}


# ── Internal helpers ───────────────────────────────────────────────────────

def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _corner_point(corner: str, bbox) -> tuple[float, float]:
    dx, dy = CORNERS[corner]
    cx = (bbox.XMin + bbox.XMax) / 2.0
    cy = (bbox.YMin + bbox.YMax) / 2.0
    rx = (bbox.XMax - bbox.XMin) / 2.0
    ry = (bbox.YMax - bbox.YMin) / 2.0
    return (cx + dx * rx, cy + dy * ry)


def _classify_position(pt: tuple[float, float], bbox) -> str:
    cx = (bbox.XMin + bbox.XMax) / 2.0
    cy = (bbox.YMin + bbox.YMax) / 2.0
    hx = (bbox.XMax - bbox.XMin) / 2.0 or 1.0
    hy = (bbox.YMax - bbox.YMin) / 2.0 or 1.0
    ndx = (pt[0] - cx) / hx
    ndy = (pt[1] - cy) / hy
    best, best_dot = "bottom-left", -float("inf")
    for name, (ddx, ddy) in CORNERS.items():
        dot = ndx * ddx + ndy * ddy
        if dot > best_dot:
            best_dot, best = dot, name
    return best


def _centroid(indices: frozenset[int], points: list[tuple[float, float]]) -> tuple[float, float]:
    xs = [points[i][0] for i in indices]
    ys = [points[i][1] for i in indices]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _fail(reason: str) -> dict:
    return {
        "path": None, "selected": None, "selected_count": 0,
        "jumps": [], "failure": reason,
        "minus_achieved": None, "plus_achieved": None,
    }


# ── Serpentine path builder ────────────────────────────────────────────────

def _build_path(
    points: list[tuple[float, float]],
    pitch_y: float,
    angle_deg: float,
    start_corner: str,
) -> list[int]:
    """Return point *indices* in serpentine order starting near *start_corner*.

    Uses ``cluster_rows`` to extract hex rows, then traverses them in
    alternating direction.  The start corner controls:
      - vertical component  → which row is row 0 (bottom or top)
      - horizontal component → which direction row 0 goes (left-to-right or reversed)
    """
    rows_of_pts = cluster_rows(points, pitch_y, angle_deg=angle_deg)
    # rows_of_pts: list[list[(x, y)]], each row sorted left-to-right in grid frame,
    # overall sorted bottom-to-top (ascending perpendicular coordinate).

    # Build a point→index lookup so we can convert back to indices.
    pt_to_idx: dict[tuple[float, float], int] = {pt: i for i, pt in enumerate(points)}

    # Convert to index rows.
    rows: list[list[int]] = [
        [pt_to_idx[pt] for pt in row]
        for row in rows_of_pts
    ]

    dx, dy = CORNERS[start_corner]

    # Vertical order: dy > 0 → start from top row
    if dy > 0:
        rows = list(reversed(rows))

    # Horizontal direction of the first row:
    # dx > 0 (right corner) → first row goes right-to-left (reversed)
    first_reversed = (dx > 0)

    path: list[int] = []
    for i, row in enumerate(rows):
        even = (i % 2 == 0)
        if even != first_reversed:
            path.extend(row)
        else:
            path.extend(reversed(row))

    return path


# ── Public API ─────────────────────────────────────────────────────────────

def serpentine_solutions(
    points: list[tuple[float, float]],
    pitch_y: float,
    angle_deg: float,
    target_s: int,
    target_p: int,
    minus_corner: str,
    plus_corner: str,
    bbox,
    top_n: int = 5,
) -> list[dict]:
    """Find up to *top_n* distinct S×P serpentine layouts, sorted best→worst.

    Searches all 8 start corners × P cell offsets.  Duplicate cell assignments
    (same set of cells per group, different start corner) are deduplicated.

    Returns the same result-dict format as ``find_series_path`` in graph.py so
    the rest of the pipeline (drawing, nav bar, console report) is unchanged.
    """
    total = target_s * target_p
    if len(points) < total:
        return [_fail("not_enough_candidates")]

    minus_pt = _corner_point(minus_corner, bbox)
    plus_pt  = _corner_point(plus_corner,  bbox)

    candidates: list[tuple[float, dict]] = []
    seen: set[frozenset] = set()

    for start_corner in CORNERS:
        path = _build_path(points, pitch_y, angle_deg, start_corner)
        if len(path) < total:
            continue

        # Try P different offsets so group boundaries land at different positions.
        for offset in range(target_p):
            tail = path[offset:]
            if len(tail) < total:
                break

            groups: list[frozenset[int]] = [
                frozenset(tail[s * target_p: (s + 1) * target_p])
                for s in range(target_s)
            ]

            # Deduplicate
            key = frozenset(frozenset(g) for g in groups)
            if key in seen:
                continue
            seen.add(key)

            # Build selected-cell list (same format as graph.py)
            selected: list[dict] = []
            for s_idx, group in enumerate(groups, start=1):
                ordered = sorted(group, key=lambda i: points[i][0])
                for p_idx, cell_idx in enumerate(ordered, start=1):
                    x, y = points[cell_idx]
                    selected.append({
                        "series": s_idx, "parallel": p_idx,
                        "x": x, "y": y,
                    })

            first_c = _centroid(groups[0],  points)
            last_c  = _centroid(groups[-1], points)

            score = (
                _dist(first_c, minus_pt) * 1000
                + _dist(last_c,  plus_pt) * 100
            )

            candidates.append((score, {
                "path":           groups,
                "selected":       selected,
                "selected_count": len(selected),
                "jumps":          [],
                "failure":        None,
                "minus_achieved": _classify_position(first_c, bbox),
                "plus_achieved":  _classify_position(last_c,  bbox),
                "_score":         score,
            }))

    if not candidates:
        return [_fail("not_enough_candidates")]

    candidates.sort(key=lambda x: x[0])
    results = []
    for _, r in candidates[:top_n]:
        r.pop("_score", None)
        results.append(r)
    return results
