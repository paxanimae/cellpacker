"""
cellpacker.layout.graph
~~~~~~~~~~~~~~~~~~~~~~~
Graph-based S×P group selection.

Candidate cell positions are modelled as a graph:
  Nodes  = cell indices into the points list
  Edges  = hex adjacency (centre-to-centre distance ≤ pitch_x × 1.05)

The selection problem is finding an ordered sequence of S connected
P-clusters (one cluster per series group) where:
  - Every cell in a cluster is connected to at least one other cell in
    the same cluster (connectivity within a group).
  - Adjacent clusters in the series chain share at least one hex-neighbour
    pair across the boundary (adjacency between groups).
  - No cell is used in more than one cluster.
  - The first cluster is as close as possible to the PACK− target corner.
  - The last cluster is as close as possible to the PACK+ target corner.

When no adjacent path exists and the user has enabled jumps, the algorithm
allows a non-adjacent step and flags it in the result.
"""

from __future__ import annotations
import math

# 8-position compass: name → normalised (dx, dy)
# dx: -1=left  0=centre  +1=right
# dy: -1=bottom  0=centre  +1=top
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

# Human-readable failure messages surfaced to the user
FAILURE_MESSAGES: dict[str, str] = {
    "not_enough_candidates": (
        "Not enough candidate cells for the requested S×P count.\n"
        "Try a smaller pack, a larger sketch, or a smaller cell diameter."
    ),
    "no_adjacent_path": (
        "No adjacent path found between series groups.\n"
        "The geometry may have a gap that breaks the chain.\n"
        "Enable 'Allow jumps' to let the algorithm cross gaps."
    ),
    "dead_end": (
        "The series path reached a dead end before completing.\n"
        "The sketch boundary may be too irregular for this S×P.\n"
        "Enable 'Allow jumps' or reduce S/P count."
    ),
}


# ── Internal helpers ───────────────────────────────────────────────────────

def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _centroid(cluster: frozenset[int], points: list[tuple[float, float]]) -> tuple[float, float]:
    xs = [points[i][0] for i in cluster]
    ys = [points[i][1] for i in cluster]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _corner_point(corner: str, bbox) -> tuple[float, float]:
    """Absolute (x, y) of *corner* within *bbox*."""
    dx, dy = CORNERS[corner]
    cx = (bbox.XMin + bbox.XMax) / 2.0
    cy = (bbox.YMin + bbox.YMax) / 2.0
    rx = (bbox.XMax - bbox.XMin) / 2.0
    ry = (bbox.YMax - bbox.YMin) / 2.0
    return (cx + dx * rx, cy + dy * ry)


def _classify_position(pt: tuple[float, float], bbox) -> str:
    """Return the compass name whose direction best matches *pt* from bbox centre."""
    cx = (bbox.XMin + bbox.XMax) / 2.0
    cy = (bbox.YMin + bbox.YMax) / 2.0
    half_x = (bbox.XMax - bbox.XMin) / 2.0 or 1.0
    half_y = (bbox.YMax - bbox.YMin) / 2.0 or 1.0
    ndx = (pt[0] - cx) / half_x
    ndy = (pt[1] - cy) / half_y
    best_name, best_dot = "bottom-left", -float("inf")
    for name, (ddx, ddy) in CORNERS.items():
        dot = ndx * ddx + ndy * ddy
        if dot > best_dot:
            best_dot, best_name = dot, name
    return best_name


# ── Graph construction ─────────────────────────────────────────────────────

def build_adjacency_graph(
    points: list[tuple[float, float]],
    pitch_x: float,
) -> dict[int, set[int]]:
    """Return index → {neighbour indices} for all hex-adjacent cell pairs."""
    threshold_sq = (pitch_x * 1.05) ** 2
    graph: dict[int, set[int]] = {i: set() for i in range(len(points))}
    for i, (x1, y1) in enumerate(points):
        for j in range(i + 1, len(points)):
            x2, y2 = points[j]
            if (x2 - x1) ** 2 + (y2 - y1) ** 2 <= threshold_sq:
                graph[i].add(j)
                graph[j].add(i)
    return graph


# ── Cluster growth ─────────────────────────────────────────────────────────

def _grow_cluster(
    graph: dict[int, set[int]],
    seed: int,
    target_p: int,
    used: set[int],
    points: list[tuple[float, float]],
) -> frozenset[int] | None:
    """Grow a compact connected P-cluster from *seed*, avoiding *used* cells.

    At each step picks the frontier cell closest to the current cluster
    centroid.  This produces a roughly-circular blob rather than an elongated
    strip, which is the correct physical shape for a series group.

    Direction is controlled by the *seed* choice at the call site — the
    caller sorts frontier seeds by distance to the next waypoint.

    Returns None if a full P-cluster cannot be formed.
    """
    available = set(range(len(points))) - used
    if seed not in available:
        return None

    cluster: set[int] = {seed}
    frontier: set[int] = graph[seed] & available

    while len(cluster) < target_p:
        if not frontier:
            return None
        cx = sum(points[c][0] for c in cluster) / len(cluster)
        cy = sum(points[c][1] for c in cluster) / len(cluster)
        next_cell = min(frontier, key=lambda c: _dist(points[c], (cx, cy)))
        cluster.add(next_cell)
        frontier.discard(next_cell)
        frontier |= (graph[next_cell] & available) - cluster

    return frozenset(cluster)


# ── Path scoring ───────────────────────────────────────────────────────────

def _score_path(
    path: list[frozenset[int]],
    points: list[tuple[float, float]],
    minus_pt: tuple[float, float],
    plus_pt: tuple[float, float],
) -> float:
    """Lower is better.

    Priority order (reflected by weight magnitudes):
      1. PACK− placement (×1000)
      2. PACK+ placement (×100)
      3. Compactness — mean step length (×10)
    """
    c_start = _centroid(path[0], points)
    c_end   = _centroid(path[-1], points)

    centroids = [_centroid(cl, points) for cl in path]
    if len(centroids) > 1:
        step_lengths = [_dist(centroids[i], centroids[i + 1])
                        for i in range(len(centroids) - 1)]
        compactness = sum(step_lengths) / len(step_lengths)
    else:
        compactness = 0.0

    return (
        _dist(c_start, minus_pt) * 1000
        + _dist(c_end,  plus_pt) * 100
        + compactness            * 80
    )


# ── Public API ─────────────────────────────────────────────────────────────

def find_series_path(
    points: list[tuple[float, float]],
    pitch_x: float,
    target_s: int,
    target_p: int,
    minus_corner: str,
    plus_corner: str,
    allow_jumps: bool,
    bbox,
    n_starts: int = 30,
    top_n: int = 5,
) -> list[dict]:
    """Find up to *top_n* distinct S×P series paths through *points*.

    Returns a list of result dicts sorted best→worst.  Each dict has:

    path            list[frozenset[int]] | None — ordered clusters
    selected        list[dict] | None           — cell dicts (series/parallel/x/y)
    selected_count  int
    jumps           list[int]                   — 1-based step numbers that used jumps
    failure         str | None                  — key into FAILURE_MESSAGES, or None
    minus_achieved  str | None                  — compass name where PACK− landed
    plus_achieved   str | None                  — compass name where PACK+ landed

    On complete failure, returns a single-element list containing a failure dict.
    Duplicate paths (same cell sets) are deduplicated so each alternative is
    genuinely different.
    """
    n = len(points)

    if n < target_s * target_p:
        return [_fail("not_enough_candidates")]

    graph = build_adjacency_graph(points, pitch_x)
    minus_pt = _corner_point(minus_corner, bbox)
    plus_pt  = _corner_point(plus_corner,  bbox)

    def _waypoint(step: int) -> tuple[float, float]:
        t = step / max(target_s - 1, 1)
        return (
            minus_pt[0] + (plus_pt[0] - minus_pt[0]) * t,
            minus_pt[1] + (plus_pt[1] - minus_pt[1]) * t,
        )

    starts = sorted(range(n), key=lambda i: _dist(points[i], minus_pt))

    # (score, result) heap kept trimmed to top_n
    candidates: list[tuple[float, dict]] = []
    seen_paths: set[frozenset] = set()
    last_failure = "no_adjacent_path"

    for seed in starts[:n_starts]:
        used: set[int] = set()
        first = _grow_cluster(graph, seed, target_p, used, points)
        if first is None:
            continue

        used |= first
        path: list[frozenset[int]] = [first]
        jumps: list[int] = []
        failure: str | None = None

        for step in range(1, target_s):
            wp = _waypoint(step)

            frontier: set[int] = set()
            for c in path[-1]:
                frontier |= graph[c] - used

            next_cluster: frozenset[int] | None = None

            for fseed in sorted(frontier, key=lambda c: _dist(points[c], wp)):
                nc = _grow_cluster(graph, fseed, target_p, used, points)
                if nc is not None:
                    next_cluster = nc
                    break

            if next_cluster is None:
                if allow_jumps:
                    unused = set(range(n)) - used
                    if not unused:
                        failure = "dead_end"
                        break
                    jseed = min(unused, key=lambda c: _dist(points[c], wp))
                    next_cluster = _grow_cluster(graph, jseed, target_p, used, points)
                    if next_cluster is None:
                        failure = "dead_end"
                        break
                    jumps.append(step + 1)
                else:
                    failure = "no_adjacent_path" if frontier else "dead_end"
                    break

            used |= next_cluster
            path.append(next_cluster)

        if failure is not None or len(path) < target_s:
            last_failure = failure or "dead_end"
            continue

        # Skip duplicate arrangements
        path_key = frozenset(frozenset(cl) for cl in path)
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)

        score = _score_path(path, points, minus_pt, plus_pt)
        selected = path_to_selected_cells(path, points)
        result = {
            "path":           path,
            "selected":       selected,
            "selected_count": len(selected),
            "jumps":          jumps,
            "failure":        None,
            "minus_achieved": _classify_position(_centroid(path[0],  points), bbox),
            "plus_achieved":  _classify_position(_centroid(path[-1], points), bbox),
            "_score":         score,
        }
        candidates.append((score, result))
        candidates.sort(key=lambda x: x[0])
        if len(candidates) > top_n:
            candidates = candidates[:top_n]

    if not candidates:
        return [_fail(last_failure)]

    results = []
    for _, r in candidates:
        r.pop("_score", None)
        results.append(r)
    return results


def path_to_selected_cells(
    path: list[frozenset[int]],
    points: list[tuple[float, float]],
) -> list[dict]:
    """Convert a series path to the cell-dict list used by the drawing stack."""
    selected = []
    for s_idx, cluster in enumerate(path, start=1):
        ordered = sorted(cluster, key=lambda i: points[i][0])
        for p_idx, cell_idx in enumerate(ordered, start=1):
            x, y = points[cell_idx]
            selected.append({"series": s_idx, "parallel": p_idx, "x": x, "y": y})
    return selected


def _fail(reason: str) -> dict:
    return {
        "path": None, "selected": None, "selected_count": 0,
        "jumps": [], "failure": reason,
        "minus_achieved": None, "plus_achieved": None,
    }
