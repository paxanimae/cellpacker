"""
cellpacker.layout.serpentine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Serpentine (boustrophedon) layout algorithm.

Three-level placement
---------------------
1. **Column width** k – number of groups per row.  k=1 → rows are exactly P
   cells wide (one group per row, maximally compact).  k=2 → two groups per
   row, k=4 → four per row, etc.  This controls the aspect ratio of each
   individual series group and of the whole pack region.

2. **Row window** – a contiguous slice of R hex rows.  R = ceil(S/k) rows
   are needed to hold S groups at k groups per row.  Trying every r_start
   explores all vertical positions for that (k, R) combination.

3. **Column window** – a sliding window of exactly k×P cells taken from each
   row.  Trying every col_start explores all horizontal positions.

Together the three levels find the most compact placement of exactly S×P
cells with groups that are as close to square as possible, without ever
hard-coding a corner or assuming the sketch is fully used.

Within a chosen region the serpentine guarantees by construction:
  • Connected groups          consecutive cells in a row are hex-adjacent
  • Short bridges             consecutive groups share a row or row-edge boundary
  • No busbar crossings       path order == wiring order
  • Predictable terminals     start of path ≈ PACK−, end ≈ PACK+

Degraded mode
-------------
If the requested S×P cannot be satisfied (too few candidates, or no valid
window), the search is re-run with reduced targets — preferring to keep P
(group capacity) and maximizing total cell count — and the best achievable
layout is returned, flagged via the ``failure`` field so the UI can tell the
user what was requested vs. what was found.
"""

from __future__ import annotations
import math

from cellpacker.layout.rows import cluster_rows
from cellpacker.geometry.transforms import rotate_2d


# 8-position compass  (dx, dy) normalised direction vectors
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


def _centroid(indices, points: list[tuple[float, float]]) -> tuple[float, float]:
    xs = [points[i][0] for i in indices]
    ys = [points[i][1] for i in indices]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _fail(reason: str) -> dict:
    return {
        "path": None, "selected": None, "selected_count": 0,
        "jumps": [], "failure": reason,
        "minus_achieved": None, "plus_achieved": None,
        "achieved_s": 0, "achieved_p": 0,
    }


# ── Serpentine path builder ────────────────────────────────────────────────

def _build_path_from_rows(
    window_rows: list[list[int]],
    start_corner: str,
) -> list[int]:
    """Build a boustrophedon path from a list of pre-clustered index rows.

    *window_rows* must be sorted bottom-to-top with cells sorted
    left-to-right within each row.

    *start_corner* controls:
      dy > 0  → start from the top row (reversed row order)
      dx > 0  → the first row is traversed right-to-left
    """
    dx, dy = CORNERS[start_corner]
    ordered = list(reversed(window_rows)) if dy > 0 else list(window_rows)
    first_reversed = (dx > 0)
    path: list[int] = []
    for i, row in enumerate(ordered):
        even = (i % 2 == 0)
        if even != first_reversed:
            path.extend(row)
        else:
            path.extend(reversed(row))
    return path


# ── Core search ────────────────────────────────────────────────────────────

# Score weights per layout priority: (straightness, bridge, PACK−, PACK+).
# Straightness = deviation of each P-group from a straight stick of P cells
# along one hex row.  Bridge = sum of consecutive-group centroid distances
# ≈ series busbar length; minimising it produces the ladder layout (sticks
# stacked side-by-side) when geometry allows, folding into adjacent columns
# when it doesn't.
PRIORITY_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "group_quality": (10.0, 2.0,  1.5, 1.0),   # sticks/ladder; terminals tie-break
    "terminals":     ( 2.0, 0.5, 10.0, 7.0),   # terminal corners dominate
    "balanced":      ( 5.0, 1.5,  5.0, 3.5),
}


def _score_window(
    groups: list[frozenset[int]],
    points: list[tuple[float, float]],
    rpts: list[tuple[float, float]],
    minus_pt: tuple[float, float],
    plus_pt: tuple[float, float],
    pitch_x: float,
    pitch_y: float,
    target_p: int,
    weights: tuple[float, float, float, float],
) -> tuple[float, tuple, tuple]:
    """Score one S-group window.  Returns (score, first_centroid, last_centroid).

    Lower = better.  The four criteria are weighted per the user's chosen
    layout priority (see PRIORITY_WEIGHTS).
    """
    first_c = _centroid(groups[0],  points)
    last_c  = _centroid(groups[-1], points)

    ideal_len = (target_p - 1) * pitch_x
    straight = 0.0
    bridge   = 0.0
    prev_c: tuple[float, float] | None = None
    for g in groups:
        c = _centroid(g, points)
        rxs = [rpts[i][0] for i in g]
        rys = [rpts[i][1] for i in g]
        straight += (max(rys) - min(rys))                          # row spread
        straight += max(0.0, (max(rxs) - min(rxs)) - ideal_len)    # row gaps
        if prev_c is not None:
            bridge += _dist(prev_c, c)
        prev_c = c

    w_straight, w_bridge, w_minus, w_plus = weights
    score = (
        straight * w_straight
        + bridge * w_bridge
        + _dist(first_c, minus_pt) * w_minus
        + _dist(last_c,  plus_pt) * w_plus
    )
    return score, first_c, last_c


def _stick_orders(n_rows: int, n_cols: int) -> list[list[tuple[int, int]]]:
    """All serpentine traversal orders over an R×k grid of sticks.

    Row-major orders walk along rows (sticks end-to-end), column-major
    orders stack sticks vertically and hop columns — the folded-ladder
    layout.  Both are generated; scoring picks the best.
    """
    orders: list[list[tuple[int, int]]] = []
    for rev_outer in (False, True):
        for rev_inner in (False, True):
            # Row-major: outer = rows, inner = columns
            rr = list(range(n_rows))
            if rev_outer:
                rr.reverse()
            order: list[tuple[int, int]] = []
            for i, r in enumerate(rr):
                cc = list(range(n_cols))
                if (i % 2 == 1) != rev_inner:
                    cc.reverse()
                order.extend((r, j) for j in cc)
            orders.append(order)
            # Column-major: outer = columns, inner = rows
            cc = list(range(n_cols))
            if rev_outer:
                cc.reverse()
            order = []
            for i, j in enumerate(cc):
                rr = list(range(n_rows))
                if (i % 2 == 1) != rev_inner:
                    rr.reverse()
                order.extend((r, j) for r in rr)
            orders.append(order)
    return orders


def _search(
    rows: list[list[int]],
    points: list[tuple[float, float]],
    rpts: list[tuple[float, float]],
    target_s: int,
    target_p: int,
    minus_pt: tuple[float, float],
    plus_pt: tuple[float, float],
    pitch_x: float,
    pitch_y: float,
    strict: bool,
    weights: tuple[float, float, float, float],
) -> list[tuple[float, list, tuple, tuple]]:
    """Run the three-level placement search for one (S, P) target.

    *rpts* are the candidate points rotated into the grid frame, so that
    column windows can be selected by actual x-position.  This keeps
    groups vertically aligned even when rows start at different x
    (wedges, trapezoids) — index-based slicing would skew them.

    strict=True  → every row in the column window must hold exactly C cells
                   (full rectangular sub-grid; best group quality).
    strict=False → accept ragged windows as long as the total cell count
                   suffices (irregular shapes where no rectangle fits).

    Returns a list of (score, groups, first_centroid, last_centroid),
    unsorted.  Empty list = no valid layout for these targets.
    """
    total = target_s * target_p
    n_rows = len(rows)
    candidates: list[tuple[float, list, tuple, tuple]] = []
    seen: set[frozenset] = set()

    def _try_groups(groups: list[frozenset[int]]) -> None:
        if any(len(g) < target_p for g in groups):
            return
        key = frozenset(groups)
        if key in seen:
            return
        seen.add(key)
        score, first_c, last_c = _score_window(
            groups, points, rpts, minus_pt, plus_pt,
            pitch_x, pitch_y, target_p, weights)
        candidates.append((score, groups, first_c, last_c))

    def _try_path(path: list[int], step: int) -> None:
        n = len(path)
        if n < total:
            return
        for i in range(0, n - total + 1, step):
            _try_groups([
                frozenset(path[i + s * target_p: i + (s + 1) * target_p])
                for s in range(target_s)
            ])

    for k in range(1, target_s + 1):          # groups per row
        C = k * target_p                       # column width (cells)
        R = math.ceil(target_s / k)            # rows needed
        if R > n_rows:
            continue
        W = C * pitch_x                        # column width (mm, grid frame)

        for r_start in range(n_rows - R + 1):
            window_rows = rows[r_start:r_start + R]

            # Candidate window starts: every distinct cell x-position in the
            # window (deduped to half-pitch).  Starting just left of a cell
            # guarantees that cell is the window's leftmost column.
            starts: list[float] = []
            seen_keys: set[int] = set()
            for row in window_rows:
                for i in row:
                    v = rpts[i][0]
                    key = round(v / (pitch_x / 2.0))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        starts.append(v - pitch_x * 0.25)

            for x_lo in sorted(starts):
                x_hi = x_lo + W
                sub_rows = [
                    [i for i in row if x_lo <= rpts[i][0] < x_hi]
                    for row in window_rows
                ]
                if strict:
                    if any(len(r) != C for r in sub_rows):
                        continue
                    # Form the R×k grid of sticks (straight P-cell row
                    # slices) and traverse it in every serpentine order —
                    # row-major (sticks end-to-end) and column-major
                    # (folded ladder).  Scoring picks the best.
                    sticks = [
                        [r_cells[j * target_p:(j + 1) * target_p]
                         for j in range(k)]
                        for r_cells in sub_rows
                    ]
                    for order in _stick_orders(R, k):
                        seq = [sticks[r][j] for r, j in order]
                        for i in range(0, len(seq) - target_s + 1):
                            _try_groups([frozenset(st)
                                         for st in seq[i:i + target_s]])
                else:
                    if sum(len(r) for r in sub_rows) < total:
                        continue
                    for start_corner in CORNERS:
                        _try_path(
                            _build_path_from_rows(sub_rows, start_corner),
                            target_p)

    return candidates


def _stick_search(
    rows: list[list[int]],
    points: list[tuple[float, float]],
    rpts: list[tuple[float, float]],
    target_s: int,
    target_p: int,
    minus_pt: tuple[float, float],
    plus_pt: tuple[float, float],
    pitch_x: float,
    pitch_y: float,
    weights: tuple[float, float, float, float],
) -> list[tuple[float, list, tuple, tuple]]:
    """Stick pass for irregular shapes where no rectangular window fits.

    Extracts every straight P-cell stick from the rows (greedy tiling of
    each contiguous run, at every phase offset), then snakes over the
    sticks row-major and column-major and slides an S-stick window along
    each order.  Groups stay perfect sticks even when the outline is a
    wedge or has concave bites — only the *arrangement* degrades.
    """
    # ── Extract sticks: (row_idx, mean_rx, cells) ──────────────────────────
    all_sticks: list[tuple[int, float, list[int]]] = []
    for ri, row in enumerate(rows):
        # Split the row into contiguous runs (gap > 1.5 pitch breaks a run)
        runs: list[list[int]] = []
        run: list[int] = []
        prev_rx: float | None = None
        for i in row:
            rx = rpts[i][0]
            if prev_rx is not None and rx - prev_rx > 1.5 * pitch_x:
                if len(run) >= target_p:
                    runs.append(run)
                run = []
            run.append(i)
            prev_rx = rx
        if len(run) >= target_p:
            runs.append(run)
        # Tile each run with non-overlapping sticks at every phase offset
        seen_sticks: set[tuple[int, ...]] = set()
        for run in runs:
            for phase in range(min(target_p, len(run) - target_p + 1)):
                for j in range(phase, len(run) - target_p + 1, target_p):
                    cells = run[j:j + target_p]
                    tkey = tuple(cells)
                    if tkey in seen_sticks:
                        continue
                    seen_sticks.add(tkey)
                    mean_rx = sum(rpts[c][0] for c in cells) / target_p
                    all_sticks.append((ri, mean_rx, cells))

    if len(all_sticks) < target_s:
        return []

    candidates: list[tuple[float, list, tuple, tuple]] = []
    seen: set[frozenset] = set()

    def _try_seq(seq: list[tuple[int, float, list[int]]]) -> None:
        for i in range(len(seq) - target_s + 1):
            window = seq[i:i + target_s]
            # Reject windows that reuse a cell (overlapping phase sticks)
            used: set[int] = set()
            ok = True
            for _, _, cells in window:
                for c in cells:
                    if c in used:
                        ok = False
                        break
                    used.add(c)
                if not ok:
                    break
            if not ok:
                continue
            groups = [frozenset(cells) for _, _, cells in window]
            key = frozenset(groups)
            if key in seen:
                continue
            seen.add(key)
            score, first_c, last_c = _score_window(
                groups, points, rpts, minus_pt, plus_pt,
                pitch_x, pitch_y, target_p, weights)
            candidates.append((score, groups, first_c, last_c))

    # Row-major snakes: order rows, alternate direction within each row
    by_row: dict[int, list] = {}
    for st in all_sticks:
        by_row.setdefault(st[0], []).append(st)
    row_keys = sorted(by_row)
    # Column-major snakes: bin sticks by x, alternate direction within bins
    bin_w = target_p * pitch_x
    by_col: dict[int, list] = {}
    for st in all_sticks:
        by_col.setdefault(round(st[1] / bin_w), []).append(st)
    col_keys = sorted(by_col)

    for outer_keys, items_by_key, inner_sort in (
        (row_keys, by_row, lambda st: st[1]),   # row-major: sort by x
        (col_keys, by_col, lambda st: st[0]),   # column-major: sort by row
    ):
        for rev_outer in (False, True):
            keys = list(reversed(outer_keys)) if rev_outer else list(outer_keys)
            for rev_inner in (False, True):
                seq: list[tuple[int, float, list[int]]] = []
                for idx, kkey in enumerate(keys):
                    items = sorted(items_by_key[kkey], key=inner_sort)
                    if (idx % 2 == 1) != rev_inner:
                        items.reverse()
                    seq.extend(items)
                _try_seq(seq)

    return candidates


def _search_both(rows, points, rpts, s, p,
                 minus_pt, plus_pt, pitch_x, pitch_y, weights):
    """Rectangular stick-grid search, then ragged stick pass, then the
    cell-level serpentine as last resort."""
    cands = _search(rows, points, rpts, s, p,
                    minus_pt, plus_pt, pitch_x, pitch_y,
                    strict=True, weights=weights)
    if not cands:
        cands = _stick_search(rows, points, rpts, s, p,
                              minus_pt, plus_pt, pitch_x, pitch_y, weights)
    if not cands:
        cands = _search(rows, points, rpts, s, p,
                        minus_pt, plus_pt, pitch_x, pitch_y,
                        strict=False, weights=weights)
    return cands


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
    priority: str = "group_quality",
    degrade_mode: str = "keep_p",
) -> list[dict]:
    """Find up to *top_n* distinct S×P layouts, sorted best → worst.

    *priority* selects the score weighting (see PRIORITY_WEIGHTS):
      "group_quality" — straight P-sticks / ladder first, terminals tie-break
      "terminals"     — PACK−/PACK+ placement dominates
      "balanced"      — both weighed comparably

    *degrade_mode* selects what to try when the requested S×P doesn't fit:
      "keep_p"    — preserve P, reduce S (voltage drops)
      "keep_s"    — preserve S, reduce P (capacity drops)
      "max_cells" — largest s×p that fits, any split

    A degraded result is flagged via ``failure`` with requested vs. achieved.
    """
    if not points:
        return [_fail("not_enough_candidates")]

    weights = PRIORITY_WEIGHTS.get(priority, PRIORITY_WEIGHTS["group_quality"])

    minus_pt = _corner_point(minus_corner, bbox)
    plus_pt  = _corner_point(plus_corner,  bbox)
    pitch_x  = pitch_y * 2.0 / math.sqrt(3)

    # ── Cluster candidates into rows once (reused across all attempts) ────
    # The two grid generators use opposite rotation conventions (sweep maps
    # grid→local with R(−a), the edge-anchored generator with R(+θ)), so the
    # sign needed to recover the grid frame differs.  Rather than track the
    # convention per caller, cluster with both signs and keep whichever
    # merges the points into fewer (= correctly aligned) rows.
    frame_angle = angle_deg
    rows_of_pts = cluster_rows(points, pitch_y, angle_deg=angle_deg)
    if angle_deg != -angle_deg:
        alt = cluster_rows(points, pitch_y, angle_deg=-angle_deg)
        if len(alt) < len(rows_of_pts):
            rows_of_pts = alt
            frame_angle = -angle_deg

    pt_to_idx = {pt: i for i, pt in enumerate(points)}
    rows: list[list[int]] = [
        [pt_to_idx[pt] for pt in row]
        for row in rows_of_pts
    ]

    # Points rotated into the grid frame — used for x-aligned column windows
    rpts = [rotate_2d(x, y, frame_angle) for x, y in points]

    # ── Try the requested targets first ────────────────────────────────────
    achieved_s, achieved_p = target_s, target_p
    candidates: list[tuple[float, list, tuple, tuple]] = []
    if target_s * target_p <= len(points):
        candidates = _search_both(rows, points, rpts, target_s, target_p,
                                  minus_pt, plus_pt, pitch_x, pitch_y, weights)

    # ── Degrade: nearest achievable combination per user preference ────────
    # Enumerate every (s, p) ≤ targets that fits in the candidate count;
    # the order in which combinations are tried is the user's choice.
    failure: str | None = None
    if not candidates:
        n_pts = len(points)
        if degrade_mode == "keep_p":
            # All (s, target_p) by descending s first, then lower p tiers.
            combo_key = lambda sp: (target_p - sp[1], target_s - sp[0])
        elif degrade_mode == "keep_s":
            combo_key = lambda sp: (target_s - sp[0], target_p - sp[1])
        else:  # max_cells
            combo_key = lambda sp: (-(sp[0] * sp[1]),
                                    target_p - sp[1], target_s - sp[0])
        combos = sorted(
            (
                (s, p)
                for s in range(target_s, 0, -1)
                for p in range(target_p, 0, -1)
                if s * p <= n_pts and (s, p) != (target_s, target_p)
            ),
            key=combo_key,
        )
        for s, p in combos:
            candidates = _search_both(rows, points, rpts, s, p,
                                      minus_pt, plus_pt, pitch_x, pitch_y,
                                      weights)
            if candidates:
                achieved_s, achieved_p = s, p
                failure = (
                    f"Requested {target_s}S×{target_p}P "
                    f"({target_s * target_p} cells) not achievable — "
                    f"showing nearest: {s}S×{p}P ({s * p} cells)"
                )
                break

    if not candidates:
        return [_fail("not_enough_candidates")]

    # ── Sort, materialise top_n ────────────────────────────────────────────
    candidates.sort(key=lambda x: x[0])
    results: list[dict] = []
    for _score, groups, first_c, last_c in candidates[:top_n]:
        selected: list[dict] = []
        for s_idx, group in enumerate(groups, start=1):
            ordered = sorted(group, key=lambda idx: points[idx][0])
            for p_idx, cell_idx in enumerate(ordered, start=1):
                x, y = points[cell_idx]
                selected.append({
                    "series": s_idx, "parallel": p_idx,
                    "x": x, "y": y,
                })
        results.append({
            "path":           groups,
            "selected":       selected,
            "selected_count": len(selected),
            "jumps":          [],
            "failure":        failure,
            "minus_achieved": _classify_position(first_c, bbox),
            "plus_achieved":  _classify_position(last_c,  bbox),
            "achieved_s":     achieved_s,
            "achieved_p":     achieved_p,
        })
    return results
