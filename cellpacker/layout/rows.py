"""
cellpacker.layout.rows
~~~~~~~~~~~~~~~~~~~~~~
Cluster a flat list of 2-D points into rows.

Rows are bands of equal perpendicular distance from a reference direction
(the hex-grid angle).  Passing *angle_deg* rotates all points into the
grid frame before clustering, so rows are always correctly identified
regardless of grid orientation.
"""

from __future__ import annotations
from typing import TypeAlias

from cellpacker.geometry.transforms import rotate_2d

Point: TypeAlias = tuple[float, float]
Row: TypeAlias = list[Point]


def cluster_rows(
    points: list[Point],
    pitch_y: float,
    *,
    tol: float | None = None,
    angle_deg: float = 0.0,
) -> list[Row]:
    """
    Group *points* into rows.

    Points are rotated by *angle_deg* into the grid frame so that each hex
    row lands at a distinct Y value.  Clustering is done in that rotated
    frame; the returned rows contain the original (un-rotated) coordinates.

    Default *tol* is ``pitch_y * 0.35`` — just under half the row spacing.
    Rows are returned sorted by increasing perpendicular distance from the
    reference direction; each row is sorted by position along the row.
    """
    if not points:
        return []

    if tol is None:
        tol = pitch_y * 0.35

    # Sort by rotated-Y (perpendicular distance from reference direction)
    keyed = sorted(
        ((rotate_2d(x, y, angle_deg)[1], (x, y)) for x, y in points),
        key=lambda t: t[0],
    )

    rows: list[Row] = []
    current: Row = [keyed[0][1]]
    current_ry: float = keyed[0][0]

    for ry, pt in keyed[1:]:
        if abs(ry - current_ry) <= tol:
            current.append(pt)
        else:
            rows.append(current)
            current = [pt]
            current_ry = ry
    rows.append(current)

    # Sort each row by position along the edge direction (rotated-X)
    for row in rows:
        row.sort(key=lambda p: rotate_2d(p[0], p[1], angle_deg)[0])

    return rows


def valid_rows(rows: list[Row], min_cells: int) -> list[Row]:
    return [r for r in rows if len(r) >= min_cells]
