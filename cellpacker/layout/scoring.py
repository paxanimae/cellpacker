"""
cellpacker.layout.scoring
~~~~~~~~~~~~~~~~~~~~~~~~~
Multi-term scoring function for candidate S×P cell selections.

Lower score is better.  Each term is independently weighted so users can
tune behaviour via the GUI without touching code.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cellpacker.geometry.face import point_to_boundary_distance  # noqa: F401


def score_selected(
    face,
    selected: list[dict],
    chosen_rows: list[list],
    all_points: list[tuple[float, float]],
    cfg: dict,
) -> float:
    """
    Compute a scalar score for *selected* (lower = better).

    Parameters
    ----------
    face:
        ``Part.Face`` used for boundary distance queries.
    selected:
        List of cell dicts with keys ``"x"`` and ``"y"``.
    chosen_rows:
        The actual row lists that were selected (used for row-shift term).
    all_points:
        All candidate points (used to compute global centroid).
    cfg:
        Configuration dict with weight keys.
    """
    from cellpacker.geometry.face import point_to_boundary_distance

    xs = [c["x"] for c in selected]
    ys = [c["y"] for c in selected]

    width  = max(xs) - min(xs)
    height = max(ys) - min(ys)

    n = len(all_points)
    global_cx = sum(p[0] for p in all_points) / n
    global_cy = sum(p[1] for p in all_points) / n
    sel_cx = sum(xs) / len(xs)
    sel_cy = sum(ys) / len(ys)

    row_centers = [
        sum(p[0] for p in row) / len(row) for row in chosen_rows
    ]
    row_shift_penalty = sum(
        abs(row_centers[i] - row_centers[i - 1])
        for i in range(1, len(row_centers))
    )

    boundary_margins = [
        point_to_boundary_distance(face, c["x"], c["y"]) for c in selected
    ]
    avg_boundary_margin = (
        sum(boundary_margins) / len(boundary_margins) if boundary_margins else 0.0
    )

    compact_term   = (width + height)                             * cfg["compactness_weight"]
    center_term    = (abs(sel_cx - global_cx) + abs(sel_cy - global_cy)) * cfg["center_bias_weight"]
    row_term       = row_shift_penalty                            * cfg["row_shift_weight"]
    boundary_term  = avg_boundary_margin                          * cfg["boundary_margin_penalty_weight"]
    usage_term     = (
        -len(selected) * cfg["shape_usage_weight"]
        if cfg["prefer_shape_usage"] else 0.0
    )

    return compact_term + center_term + row_term + boundary_term + usage_term
