"""
cellpacker.layout.architect
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Architecture-first pack layout.

Design intent (agreed with the user, 2026-06-13)
------------------------------------------------
All architecture inputs are PREFERENCES, not constraints:

Group shape    preferred arrangement of the P cells of one group:
                 "line"  — 1 row × P cells
                 "block" — closest-to-square tile (P=4 → 2×2)
               Groups that collide with the boundary deform *toward* the
               preference (an L instead of a 2×2, a bent line instead of a
               straight one) — never random scatter, and never a wholesale
               fallback to a different algorithm.
Series path    preferred chaining: "straight" (no folds) / "u_fold" (one
               fold) / "auto".  Geometry may force extra folds; mismatch is
               penalised in scoring, not forbidden.
Terminal ends  where PACK− / PACK+ sit ON THE PACK: same_end / opposite_ends.
Terminal side  which side of the pack the PACK− terminal faces.
Pack position  where the pack sits inside the boundary.

Engine
------
1. **Rigid stamp** — the exact ideal template (perfect tiles, perfect
   lanes) slid over the candidate grid.  Wins whenever space allows.
2. **Growth** — groups grown one at a time, each preferring the requested
   shape, the chain following the series-path direction and folding where
   the boundary forces it.  Handles wedges and freeform outlines.
3. **Degradation** — if S×P cannot be completed even with deformed groups,
   smaller (s, p) combinations are tried per the user's fit-fallback
   choice (keep P / keep S / max cells).

All produced layouts are scored with one unified function whose weights
come from the user's layout priority; the best top_n are returned.

Grid encoding
-------------
Candidates map to integer (r, h): r = hex row, h = half-column.  Cells in
row r share h-parity, alternating with r, so hex neighbours are
(r, h±2) and (r±1, h±1).
"""

from __future__ import annotations
import math

from cellpacker.layout.rows import cluster_rows
from cellpacker.geometry.transforms import rotate_2d


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

OPPOSITE: dict[str, str] = {
    "left": "right", "right": "left", "top": "bottom", "bottom": "top",
    "top-left": "bottom-right", "bottom-right": "top-left",
    "top-right": "bottom-left", "bottom-left": "top-right",
}

# Score weights per layout priority:
# (shape fidelity, bridge length, terminal fit, pack position)
PRIORITY_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "group_quality": (10.0, 2.0,  1.5, 1.0),
    "terminals":     ( 2.0, 0.5, 10.0, 7.0),
    "balanced":      ( 5.0, 1.5,  5.0, 3.5),
}


# ── Grid helpers ───────────────────────────────────────────────────────────

def _hex_neighbors(r: int, h: int):
    return ((r, h - 2), (r, h + 2),
            (r - 1, h - 1), (r - 1, h + 1),
            (r + 1, h - 1), (r + 1, h + 1))


def block_dims(p: int) -> tuple[int, int]:
    """Closest-to-square (rows, cols) tile with rows*cols == p, rows ≤ cols."""
    best = (1, p)
    for r in range(1, int(math.sqrt(p)) + 1):
        if p % r == 0:
            best = (r, p // r)
    return best


def _detect_frame_angle(points, pitch_y, angle_deg) -> float:
    """Pick the rotation sign that clusters candidates into fewer rows."""
    if angle_deg == 0.0:
        return 0.0
    a = cluster_rows(points, pitch_y, angle_deg=angle_deg)
    b = cluster_rows(points, pitch_y, angle_deg=-angle_deg)
    return angle_deg if len(a) <= len(b) else -angle_deg


def _classify_position(pt, bbox) -> str:
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


# ── Shape fidelity ─────────────────────────────────────────────────────────

def _blob_pen(coords: list[tuple[float, float]]) -> float:
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    return sum(math.hypot(x - cx, y - cy) for x, y in coords)


_IDEAL_BLOCK_CACHE: dict[tuple[int, float, float], float] = {}


def _ideal_block_pen(P: int, px: float, py: float) -> float:
    """Blob penalty of the most compact P-cell cluster on an empty hex grid
    — the reference against which real block groups are measured."""
    key = (P, px, py)
    if key in _IDEAL_BLOCK_CACHE:
        return _IDEAL_BLOCK_CACHE[key]
    cells = {(0, 0)}

    def coords(cs):
        return [(h * px / 2.0, r * py) for r, h in cs]

    while len(cells) < P:
        frontier = {n for c in cells for n in _hex_neighbors(*c)} - cells
        best = min(frontier, key=lambda c: _blob_pen(coords(cells | {c})))
        cells.add(best)
    val = _blob_pen(coords(cells))
    _IDEAL_BLOCK_CACHE[key] = val
    return val


def _group_shape_pen(
    idxs, rpts, prefer: str, P: int, px: float, py: float,
) -> float:
    """How far one group deviates from the preferred shape (0 = ideal)."""
    xs = [rpts[i][0] for i in idxs]
    ys = [rpts[i][1] for i in idxs]
    line_pen = ((max(ys) - min(ys)) * 3.0
                + max(0.0, (max(xs) - min(xs)) - (P - 1) * px))
    if prefer == "line":
        return line_pen
    block_pen = max(0.0, _blob_pen(list(zip(xs, ys)))
                    - _ideal_block_pen(P, px, py))
    if prefer == "block":
        return block_pen
    return min(line_pen, block_pen)       # auto: either shape counts as ideal


# ── Unified scoring ────────────────────────────────────────────────────────

def _score_solution(
    groups: list[list[int]],
    points, rpts,
    prefer_shape: str, series_path: str,
    terminal_ends: str, terminal_side: str,
    pack_position: str, bbox,
    P: int, px: float, py: float,
    folds: int,
    weights: tuple[float, float, float, float],
) -> float:
    w_shape, w_bridge, w_term, w_pos = weights

    shape_total = sum(
        _group_shape_pen(g, rpts, prefer_shape, P, px, py) for g in groups)

    cents = []
    for g in groups:
        cents.append((sum(points[i][0] for i in g) / len(g),
                      sum(points[i][1] for i in g) / len(g)))
    bridge = sum(math.dist(cents[i], cents[i + 1])
                 for i in range(len(cents) - 1))

    # Terminal fit: pack-relative distance of first/last group to the side
    all_idx = [i for g in groups for i in g]
    xs = [points[i][0] for i in all_idx]
    ys = [points[i][1] for i in all_idx]
    pminx, pmaxx, pminy, pmaxy = min(xs), max(xs), min(ys), max(ys)

    def _side_pen(cent, side):
        dx, dy = CORNERS[side]
        pen = 0.0
        if dx:
            pen += abs((pmaxx if dx > 0 else pminx) - cent[0])
        if dy:
            pen += abs((pmaxy if dy > 0 else pminy) - cent[1])
        return pen

    term_pen = 0.0
    if terminal_side in CORNERS:
        term_pen += _side_pen(cents[0], terminal_side)
        plus_side = (terminal_side if terminal_ends == "same_end"
                     else OPPOSITE[terminal_side])
        term_pen += _side_pen(cents[-1], plus_side)

    pos_pen = 0.0
    if bbox is not None and pack_position not in ("anywhere", None):
        if pack_position == "center":
            tx = (bbox.XMin + bbox.XMax) / 2.0
            ty = (bbox.YMin + bbox.YMax) / 2.0
        else:
            dx, dy = CORNERS.get(pack_position, (0, 0))
            tx = ((bbox.XMin + bbox.XMax) / 2.0
                  + dx * (bbox.XMax - bbox.XMin) / 2.0)
            ty = ((bbox.YMin + bbox.YMax) / 2.0
                  + dy * (bbox.YMax - bbox.YMin) / 2.0)
        pcx = sum(c[0] for c in cents) / len(cents)
        pcy = sum(c[1] for c in cents) / len(cents)
        pos_pen = math.hypot(pcx - tx, pcy - ty)

    # Series-path preference: penalise fold-count mismatch, not forbid it
    path_pen = 0.0
    if series_path == "straight":
        path_pen += folds * P * px * 2.0
    elif series_path == "u_fold":
        path_pen += abs(folds - 1) * P * px * 2.0
    if terminal_ends == "same_end" and folds % 2 == 0:
        path_pen += P * px * 2.0
    elif terminal_ends == "opposite_ends" and folds % 2 == 1:
        path_pen += P * px * 2.0

    return (shape_total * w_shape + bridge * w_bridge
            + term_pen * w_term + pos_pen * w_pos + path_pen)


# ── Engine 1: rigid template stamp ─────────────────────────────────────────

def _line_template(S, P, n_lanes):
    G = math.ceil(S / n_lanes)
    groups = []
    for L in range(n_lanes):
        order = list(range(G))
        if L % 2 == 1:
            order.reverse()
        for i in order:
            if len(groups) >= S:
                break
            groups.append([(i, 2 * (L * P + k) + (i % 2)) for k in range(P)])
    return groups


def _block_template(S, P, n_lanes):
    bh, bw = block_dims(P)
    if bh == 1:
        return None
    G = math.ceil(S / n_lanes)
    groups = []
    for L in range(n_lanes):
        base_r = L * bh
        order = list(range(G))
        if L % 2 == 1:
            order.reverse()
        for i in order:
            if len(groups) >= S:
                break
            cells = []
            for rr in range(bh):
                dr = base_r + rr
                for cc in range(bw):
                    cells.append((dr, 2 * (i * bw + cc) + (dr % 2)))
            groups.append(cells)
    return groups


def _lane_counts(series_path, terminal_ends, S):
    if series_path == "straight":
        counts = [1]
    elif series_path == "u_fold":
        counts = [2]
    else:
        counts = [n for n in (1, 2, 3, 4) if n <= S]
    if terminal_ends == "same_end":
        counts = [n for n in counts if n % 2 == 0]
    elif terminal_ends == "opposite_ends":
        counts = [n for n in counts if n % 2 == 1]
    return counts


def _rigid_placements(occ, S, P, group_shape, series_path, terminal_ends):
    """Yield (groups_as_idx_lists, folds) for every rigid-template fit."""
    shapes = ([group_shape] if group_shape in ("line", "block")
              else ["block", "line"])
    if shapes == ["block"] and block_dims(P)[0] == 1:
        shapes = ["line"]
    out = []
    seen = set()
    for shape in shapes:
        for n in _lane_counts(series_path, terminal_ends, S):
            tpl = (_line_template(S, P, n) if shape == "line"
                   else _block_template(S, P, n))
            if tpl is None:
                continue
            flat = [(gi, dr, dh) for gi, cells in enumerate(tpl)
                    for dr, dh in cells]
            for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                for (r0, h0) in occ:
                    placed = [[] for _ in tpl]
                    ok = True
                    for gi, dr, dh in flat:
                        idx = occ.get((r0 + sy * dr, h0 + sx * dh))
                        if idx is None:
                            ok = False
                            break
                        placed[gi].append(idx)
                    if not ok:
                        continue
                    key = tuple(tuple(sorted(g)) for g in placed)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append((placed, n - 1))
    return out


# ── Engine 2: group-by-group growth ────────────────────────────────────────

def _grow_group(seed, P, used, occ, rpts, prefer, px, py):
    """Grow one group from *seed*, adding the unused neighbour that keeps
    the group closest to the preferred shape.  Returns cell list or None."""
    group = [seed]
    cells = {seed}
    while len(group) < P:
        frontier = set()
        for c in group:
            for n in _hex_neighbors(*c):
                if n in occ and n not in used and n not in cells:
                    frontier.add(n)
        if not frontier:
            return None
        idx_of = lambda c: occ[c]
        best, best_pen = None, float("inf")
        for cand in frontier:
            trial = [idx_of(c) for c in group] + [idx_of(cand)]
            pen = _group_shape_pen(trial, rpts, prefer, P, px, py)
            if pen < best_pen:
                best_pen, best = pen, cand
        group.append(best)
        cells.add(best)
    return group


def _grow_run(seed, S, P, occ, rpts, prefer, d1, d2, px, py):
    """Grow a full S-group chain.  d1 = series direction (grid frame),
    d2 = fold direction.  Returns (groups_idx, folds) or None."""
    used: set = set()
    groups_idx: list[list[int]] = []
    groups_rh:  list[list[tuple[int, int]]] = []
    folds = 0
    d1cur = d1
    cur_seed = seed

    def proj(cell, d):
        x, y = rpts[occ[cell]]
        return x * d[0] + y * d[1]

    def frontier_of(cell_groups):
        out = set()
        for grp in cell_groups:
            for c in grp:
                for n in _hex_neighbors(*c):
                    if n in occ and n not in used:
                        out.add(n)
            if out:
                break                      # nearest groups first
        return out

    for s in range(S):
        g = _grow_group(cur_seed, P, used, occ, rpts, prefer, px, py)
        if g is None:
            return None
        used.update(g)
        groups_rh.append(g)
        groups_idx.append([occ[c] for c in g])
        if s == S - 1:
            break
        # Next seed: unused neighbour of this group, furthest along d1
        frontier = frontier_of([g])
        if frontier:
            cur_seed = max(frontier, key=lambda c: proj(c, d1cur))
        else:
            # Fold: walk back along the chain to find open space, step in
            # d2 (the fold direction), reverse the series direction.
            frontier = frontier_of(reversed(groups_rh))
            if not frontier:
                return None
            folds += 1
            d1cur = (-d1cur[0], -d1cur[1])
            cur_seed = max(frontier, key=lambda c: proj(c, d2))
    return groups_idx, folds


def _grown_placements(occ, points, rpts, S, P,
                      group_shape, terminal_side, px, py,
                      max_seeds: int = 8):
    """Run growth from several seeds and direction configs."""
    prefer = group_shape if group_shape in ("line", "block") else "auto"

    # Seeds: candidates most extreme toward the terminal side (local frame)
    sx, sy = CORNERS.get(terminal_side, (-1, 0))
    ranked = sorted(occ.items(),
                    key=lambda kv: -(points[kv[1]][0] * sx
                                     + points[kv[1]][1] * sy))
    seeds = [rh for rh, _ in ranked[:max_seeds]]

    configs = []
    for d1 in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for s2 in (1, -1):
            d2 = (-d1[1] * s2, d1[0] * s2)
            configs.append((d1, d2))

    out = []
    seen = set()
    for seed in seeds:
        for d1, d2 in configs:
            res = _grow_run(seed, S, P, occ, rpts, prefer, d1, d2, px, py)
            if res is None:
                continue
            groups, folds = res
            key = tuple(tuple(sorted(g)) for g in groups)
            if key in seen:
                continue
            seen.add(key)
            out.append((groups, folds))
    return out


# ── Public API ─────────────────────────────────────────────────────────────

def architecture_solutions(
    points: list[tuple[float, float]],
    pitch_y: float,
    angle_deg: float,
    target_s: int,
    target_p: int,
    group_shape: str = "auto",
    series_path: str = "auto",
    terminal_ends: str = "auto",
    terminal_side: str = "left",
    pack_position: str = "anywhere",
    bbox=None,
    top_n: int = 5,
    priority: str = "group_quality",
    degrade_mode: str = "keep_p",
) -> list[dict]:
    """Architecture-first layout: rigid stamp → growth → degraded S×P.

    Returns up to *top_n* solution dicts, or [] only when nothing can be
    placed at all (caller may fall back to the adaptive search).
    """
    if not points:
        return []

    pitch_x = pitch_y * 2.0 / math.sqrt(3)
    frame_angle = _detect_frame_angle(points, pitch_y, angle_deg)
    rpts = [rotate_2d(x, y, frame_angle) for x, y in points]
    weights = PRIORITY_WEIGHTS.get(priority, PRIORITY_WEIGHTS["group_quality"])

    ry0 = min(p[1] for p in rpts)
    occ: dict[tuple[int, int], int] = {}
    for idx, (rx, ry) in enumerate(rpts):
        r = round((ry - ry0) / pitch_y)
        h = round(2.0 * rx / pitch_x)
        occ[(r, h)] = idx

    def _attempt(s: int, p: int):
        """All placements for one (s, p): rigid first, growth always."""
        if s * p > len(points):
            return []
        results = [(g, f, "rigid") for g, f in
                   _rigid_placements(occ, s, p, group_shape,
                                     series_path, terminal_ends)]
        results += [(g, f, "grown") for g, f in
                    _grown_placements(occ, points, rpts, s, p,
                                      group_shape, terminal_side,
                                      pitch_x, pitch_y)]
        return results

    achieved_s, achieved_p = target_s, target_p
    failure: str | None = None
    placements = _attempt(target_s, target_p)

    if not placements:
        if degrade_mode == "keep_p":
            combo_key = lambda sp: (target_p - sp[1], target_s - sp[0])
        elif degrade_mode == "keep_s":
            combo_key = lambda sp: (target_s - sp[0], target_p - sp[1])
        else:
            combo_key = lambda sp: (-(sp[0] * sp[1]),
                                    target_p - sp[1], target_s - sp[0])
        combos = sorted(
            ((s, p)
             for s in range(target_s, 0, -1)
             for p in range(target_p, 0, -1)
             if s * p <= len(points) and (s, p) != (target_s, target_p)),
            key=combo_key,
        )
        for s, p in combos:
            placements = _attempt(s, p)
            if placements:
                achieved_s, achieved_p = s, p
                failure = (
                    f"Requested {target_s}S×{target_p}P "
                    f"({target_s * target_p} cells) not achievable — "
                    f"showing nearest: {s}S×{p}P ({s * p} cells)"
                )
                break

    if not placements:
        return []

    scored = []
    for groups, folds, method in placements:
        score = _score_solution(
            groups, points, rpts,
            group_shape, series_path, terminal_ends, terminal_side,
            pack_position, bbox, achieved_p, pitch_x, pitch_y,
            folds, weights)
        scored.append((score, groups, folds, method))
    scored.sort(key=lambda t: t[0])

    results: list[dict] = []
    for score, groups, folds, method in scored[:top_n]:
        selected = []
        for s_idx, group in enumerate(groups, start=1):
            ordered = sorted(group, key=lambda i: (points[i][1], points[i][0]))
            for p_idx, cell_idx in enumerate(ordered, start=1):
                x, y = points[cell_idx]
                selected.append({"series": s_idx, "parallel": p_idx,
                                 "x": x, "y": y})

        ideal = sum(
            1 for g in groups
            if _group_shape_pen(g, rpts, group_shape, achieved_p,
                                pitch_x, pitch_y) < 1.0)

        def _cent(group):
            return (sum(points[i][0] for i in group) / len(group),
                    sum(points[i][1] for i in group) / len(group))

        results.append({
            "path":           [frozenset(g) for g in groups],
            "selected":       selected,
            "selected_count": len(selected),
            "jumps":          [],
            "failure":        failure,
            "minus_achieved": _classify_position(_cent(groups[0]), bbox) if bbox else None,
            "plus_achieved":  _classify_position(_cent(groups[-1]), bbox) if bbox else None,
            "achieved_s":     achieved_s,
            "achieved_p":     achieved_p,
            "arch_info":      (f"{method}; shape {group_shape}: "
                               f"{ideal}/{len(groups)} groups ideal; "
                               f"{folds} fold(s)"),
        })
    return results
