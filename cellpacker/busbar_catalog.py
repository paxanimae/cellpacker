"""
cellpacker.busbar_catalog
~~~~~~~~~~~~~~~~~~~~~~~~~
Load, filter, and rank entries from busbars.json.

A busbar is a busbar — the catalog has no concept of "parallel" or "series".
Those are pack topology concerns.  The generation logic asks the catalog:
"what in-stock busbar fits this cell diameter and P count?" and gets back
a ranked list.
"""

from __future__ import annotations
import json
import math
import os

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "busbars.json")


def load_catalog(path: str = _CATALOG_PATH) -> dict:
    """Load and return the raw catalog dict from *path*."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def compatible_busbars(catalog: dict, cell_diameter: float) -> list[dict]:
    """All entries whose compatible_diameter_range includes *cell_diameter*."""
    lo_hi = lambda b: b["compatible_diameter_range"]
    return [
        b for b in catalog["busbars"]
        if lo_hi(b)[0] <= cell_diameter <= lo_hi(b)[1]
    ]


def in_stock_busbars(entries: list[dict]) -> list[dict]:
    return [b for b in entries if b.get("in_stock", False)]


def rank_by_fit(entries: list[dict], target_p: int) -> list[dict]:
    """Rank by fewest pieces needed, then highest p_rating as tiebreak."""
    def _key(b: dict) -> tuple:
        pieces = math.ceil(target_p / max(b["p_rating"], 1))
        return (pieces, -b["p_rating"])
    return sorted(entries, key=_key)


def validate_fit(catalog: dict, cell_diameter: float) -> str:
    """
    Returns one of:
      ``"ok"``               – at least one in-stock busbar fits this cell size
      ``"none_in_stock"``    – catalog has matches but none are marked in_stock
      ``"no_catalog_match"`` – no catalog entry covers this cell diameter at all
    """
    compat = compatible_busbars(catalog, cell_diameter)
    if not compat:
        return "no_catalog_match"
    if not in_stock_busbars(compat):
        return "none_in_stock"
    return "ok"


def best_fit(catalog: dict, cell_diameter: float, target_p: int) -> dict | None:
    """Return the best in-stock busbar for *cell_diameter* and *target_p*, or None."""
    candidates = in_stock_busbars(compatible_busbars(catalog, cell_diameter))
    ranked = rank_by_fit(candidates, target_p)
    return ranked[0] if ranked else None


def save_catalog(catalog: dict, path: str = _CATALOG_PATH) -> None:
    """Overwrite *path* with the current state of *catalog* as formatted JSON."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=2, ensure_ascii=False)
