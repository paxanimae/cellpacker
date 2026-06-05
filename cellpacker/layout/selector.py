"""
cellpacker.layout.selector
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Select the best contiguous S×P window from a set of candidate rows.

The algorithm:
1. Cluster all candidate points into rows.
2. Slide a window of *target_s* consecutive rows over the full row list.
3. For each window where every row has >= *target_p* cells, pick the
   *target_p* cells closest to the global X-centre from each row.
4. Score each window; keep the lowest-scoring one.
"""

from __future__ import annotations

from cellpacker.layout.rows import cluster_rows, valid_rows
from cellpacker.layout.scoring import score_selected


def select_compact_sp(
    face,
    points: list[tuple[float, float]],
    pitch_y: float,
    target_s: int,
    target_p: int,
    cfg: dict,
) -> tuple[list[dict] | None, list, list]:
    """
    Return ``(selected_cells, all_rows, valid_rows_list)``.

    *selected_cells* is ``None`` when no valid window exists.
    Each cell dict has keys: ``series``, ``parallel``, ``x``, ``y``.
    """
    rows = cluster_rows(points, pitch_y)

    if len(rows) < target_s:
        return None, rows, valid_rows(rows, target_p)

    global_cx = sum(p[0] for p in points) / len(points)

    valid_windows: list[tuple[float, list[dict]]] = []

    for start in range(len(rows) - target_s + 1):
        window = rows[start : start + target_s]

        if any(len(r) < target_p for r in window):
            continue

        chosen_rows: list[list] = []
        selected: list[dict] = []

        for s_idx, row in enumerate(window, start=1):
            ranked = sorted(row, key=lambda p, cx=global_cx: abs(p[0] - cx))
            chosen = sorted(ranked[:target_p], key=lambda p: p[0])
            chosen_rows.append(chosen)
            for p_idx, pt in enumerate(chosen, start=1):
                selected.append(
                    {"series": s_idx, "parallel": p_idx, "x": pt[0], "y": pt[1]}
                )

        score = score_selected(face, selected, chosen_rows, points, cfg)
        valid_windows.append((score, selected))

    if not valid_windows:
        return None, rows, valid_rows(rows, target_p)

    valid_windows.sort(key=lambda t: t[0])
    best_selected = valid_windows[0][1]
    return best_selected, rows, valid_rows(rows, target_p)


def build_selected_by_series(
    selected_cells: list[dict] | None,
    snake: bool = False,
) -> dict[int, list[dict]]:
    """
    Group *selected_cells* by their ``series`` key and optionally apply
    snake ordering (even-numbered series rows are reversed in X).

    Returns a dict mapping ``series_index -> [cell_dict, ...]``.
    """
    by_series: dict[int, list[dict]] = {}
    for cell in (selected_cells or []):
        by_series.setdefault(cell["series"], []).append(dict(cell))

    for s, row in by_series.items():
        row.sort(key=lambda c: c["x"])
        if snake and (s % 2 == 0):
            row.reverse()
        for idx, cell in enumerate(row, start=1):
            cell["parallel"] = idx

    return by_series
