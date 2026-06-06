"""
cellpacker.layout.rows
~~~~~~~~~~~~~~~~~~~~~~
Cluster a flat list of 2-D points into horizontal rows.
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
    Group *points* into rows by Y proximity.
    Default *tol* is ``pitch_y * 0.35``.
    Returns rows sorted ascending by Y, each row sorted ascending by X.
    """
    if not points:
        return []

    if tol is None:
        tol = pitch_y * 0.35

    pts = sorted(points, key=lambda p: p[1])

    # Diagnostic: print Y spread so we can spot coordinate system issues
    y_vals = [p[1] for p in pts]
    print(f"BatteryPackLayoutTool: clustering {len(pts)} points, "
          f"Y range [{y_vals[0]:.1f}, {y_vals[-1]:.1f}], pitch_y={pitch_y:.2f}, tol={tol:.2f}")

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

    row_sizes = [len(r) for r in rows]
    print(f"BatteryPackLayoutTool: {len(rows)} rows, sizes: {row_sizes}")

    return rows


def valid_rows(rows: list[Row], min_cells: int) -> list[Row]:
    return [r for r in rows if len(r) >= min_cells]
