"""
cellpacker.layout.sweep
~~~~~~~~~~~~~~~~~~~~~~~
Sweep over candidate angles and return the angle that produces the most
candidate cell positions.  Group selection is done separately by
cellpacker.layout.graph.find_series_path.
"""

from __future__ import annotations

from cellpacker.geometry.grid import GridParams, generate_candidate_points


def sweep_for_candidates(
    face,
    bbox,
    angle_list: list[float],
    params: GridParams,
) -> tuple[float, list[tuple[float, float]]]:
    """Try every angle; return (best_angle, candidate_points).

    "Best" means the angle that yields the most candidate positions inside
    the face.  The caller is responsible for running group selection on the
    returned points.
    """
    best_angle = angle_list[0] if angle_list else 0.0
    best_pts: list[tuple[float, float]] = []

    for angle in angle_list:
        pts = generate_candidate_points(face, bbox, angle, params)
        if len(pts) > len(best_pts):
            best_pts = pts
            best_angle = angle

    return best_angle, best_pts
