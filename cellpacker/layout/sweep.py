"""
cellpacker.layout.sweep
~~~~~~~~~~~~~~~~~~~~~~~
Sweep over a list of candidate angles, generate hex grids for each,
run S×P selection, and return the best result.
"""

from __future__ import annotations

from cellpacker.geometry.grid import GridParams, generate_candidate_points
from cellpacker.layout.selector import select_compact_sp


def _is_better(candidate: dict, best: dict, mode: str) -> bool:
    """Return ``True`` if *candidate* beats *best* under *mode*."""
    if mode == "fit":
        return len(candidate["points"]) > len(best["points"])
    # pack mode: maximise selected count, break ties by total candidates
    if candidate["selected_count"] > best["selected_count"]:
        return True
    if candidate["selected_count"] == best["selected_count"]:
        return len(candidate["points"]) > len(best["points"])
    return False


def sweep_angles(
    face,
    bbox,
    angle_list: list[float],
    params: GridParams,
    cfg: dict,
) -> dict:
    """
    Try every angle in *angle_list* and return a result dict for the best one.

    Result dict keys
    ----------------
    angle, points, rows, valid_rows, selected, selected_count
    """
    best: dict | None = None

    for angle in angle_list:
        points = generate_candidate_points(face, bbox, angle, params)
        selected, rows, vrows = select_compact_sp(
            face, points, params.pitch_y, cfg["target_s"], cfg["target_p"], cfg
        )
        result = {
            "angle": angle,
            "points": points,
            "rows": rows,
            "valid_rows": vrows,
            "selected": selected,
            "selected_count": 0 if selected is None else len(selected),
        }
        if best is None or _is_better(result, best, cfg["mode"]):
            best = result

    if best is None:
        raise RuntimeError("No angle produced any candidate points.")

    return best
