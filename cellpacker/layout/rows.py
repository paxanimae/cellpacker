"""
cellpacker.layout.rows
~~~~~~~~~~~~~~~~~~~~~~
Cluster a flat list of 2-D points into horizontal rows and provide
helpers for working with row data.
"""

from __future__ import annotations
from typing import TypeAlias

Point: TypeAlias = tuple[float, float]
Row: TypeAlias = list[Point]


def cluster_rows(
    points: list[Point],
    pitch_y: float,
    tol: float | None = None,
) -> list[Row]:
    """
    Group *points* into rows by proximity along the Y axis.

    Points within *tol* of each other in Y are considered the same row.
    Default *tol* is ``pitch_y * 0.35``, which works well for hex grids.

    Returns a list of rows sorted ascending by Y, each row sorted ascending
    by X.
    """
    if not points:
        return []

    if tol is None:
        tol = pitch_y * 0.35

    pts = sorted(points, key=lambda p: p[1])
    rows: list[Row] = []
    current: Row = [pts[0]]

    for p in pts[1:]:
        if abs(p[1] - current[-1][1]) <= tol:
            current.append(p)
        else:
            rows.append(current)
            current = [p]
    rows.append(current)

    for row in rows:
        row.sort(key=lambda p: p[0])

    return rows


def valid_rows(rows: list[Row], min_cells: int) -> list[Row]:
    """Return only rows that have at least *min_cells* points."""
    return [r for r in rows if len(r) >= min_cells]
