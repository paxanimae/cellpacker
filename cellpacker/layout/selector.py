"""
cellpacker.layout.selector
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Converts the raw output of the graph-based path search into the
series-keyed cell dict format used by the drawing stack.
"""

from __future__ import annotations


def build_selected_by_series(
    selected_cells: list[dict] | None,
) -> dict[int, list[dict]]:
    """Group *selected_cells* by their ``series`` key.

    Returns a dict mapping series_index → [cell_dict, ...].
    Each row is sorted by X and parallel indices are re-assigned 1-based.
    """
    by_series: dict[int, list[dict]] = {}
    for cell in (selected_cells or []):
        by_series.setdefault(cell["series"], []).append(dict(cell))

    for row in by_series.values():
        row.sort(key=lambda c: c["x"])
        for idx, cell in enumerate(row, start=1):
            cell["parallel"] = idx

    return by_series
