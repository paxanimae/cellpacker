"""
cellpacker.drawing.cells
~~~~~~~~~~~~~~~~~~~~~~~~~
Draw individual cells (2-D disks, 3-D cylinders, S/P labels) and manage
FreeCAD document groups for the pack hierarchy.
"""

from __future__ import annotations
import FreeCAD as App

from cellpacker.geometry.transforms import to_global
from cellpacker.drawing.primitives import draw_circle, draw_cylinder, draw_text
from cellpacker.drawing.colors import get_series_color


# ── Group helpers ─────────────────────────────────────────────────────────

def make_or_get_group(doc, name: str):
    """Return existing group named *name*, or create a new one."""
    grp = doc.getObject(name)
    if grp is None:
        grp = doc.addObject("App::DocumentObjectGroup", name)
    return grp


def _try_add(parent_group, child_group) -> None:
    try:
        parent_group.addObject(child_group)
    except Exception:
        pass


def build_pack_groups(doc, root_name: str) -> dict[str, object]:
    """
    Create (or retrieve) the standard group hierarchy for a pack run.

    Returns a dict with keys:
    ``root, all_candidates, selected, busbars, polarity, direction``
    """
    grp_root = make_or_get_group(doc, root_name)
    grp_all  = make_or_get_group(doc, root_name + "_AllCandidates")
    grp_pack = make_or_get_group(doc, root_name + "_Selected")
    grp_bus  = make_or_get_group(doc, root_name + "_Busbars")
    grp_pol  = make_or_get_group(doc, root_name + "_Polarity")
    grp_dir  = make_or_get_group(doc, root_name + "_Direction")

    for grp in (grp_pack, grp_bus, grp_pol, grp_dir):
        _try_add(grp_root, grp)

    return {
        "root": grp_root,
        "all_candidates": grp_all,
        "selected": grp_pack,
        "busbars": grp_bus,
        "polarity": grp_pol,
        "direction": grp_dir,
    }


def build_series_groups(doc, root_name: str, total_s: int, parent_group) -> dict[int, object]:
    """Create one sub-group per series index under *parent_group*."""
    series_groups: dict[int, object] = {}
    for s in range(1, total_s + 1):
        sg = make_or_get_group(doc, f"{root_name}_Series_{s:02d}")
        _try_add(parent_group, sg)
        series_groups[s] = sg
    return series_groups


# ── Cell drawing ──────────────────────────────────────────────────────────

def draw_candidate_cells(
    doc,
    sketch_obj,
    points: list[tuple[float, float]],
    radius: float,
    rotation: App.Rotation,
    group,
    cfg: dict,
) -> None:
    """Draw all candidate cell positions (gray, no label)."""
    for i, pt in enumerate(points, start=1):
        gpt = to_global(sketch_obj, pt[0], pt[1])
        if cfg["make_2d"]:
            draw_circle(doc, gpt, radius, f"CAND_{i:03d}", group, color=(0.70, 0.70, 0.70))
        if cfg["make_3d"]:
            draw_cylinder(doc, gpt, radius, cfg["cell_height"], rotation,
                          f"CAND_{i:03d}_3D", group)


def draw_selected_cell(
    doc,
    sketch_obj,
    cell: dict,
    radius: float,
    rotation: App.Rotation,
    group,
    cfg: dict,
    color: tuple,
) -> App.Vector:
    """
    Draw one selected cell (disk + optional cylinder + optional label).
    Returns the global cell-centre point.
    """
    gpt = to_global(sketch_obj, cell["x"], cell["y"])
    name = f"S{cell['series']:02d}_P{cell['parallel']:02d}"

    if cfg["make_2d"]:
        draw_circle(doc, gpt, radius, name, group, color=color)
    if cfg["make_3d"]:
        draw_cylinder(doc, gpt, radius, cfg["cell_height"], rotation,
                      name + "_3D", group, color=color)
    if cfg["make_labels"]:
        draw_text(doc, gpt, f"{cell['series']}/{cell['parallel']}",
                  name + "_TXT", group, color=color)

    return gpt


def draw_all_selected_cells(
    doc,
    sketch_obj,
    selected_by_series: dict[int, list[dict]],
    radius: float,
    rotation: App.Rotation,
    series_groups: dict[int, object],
    cfg: dict,
) -> dict[tuple[int, int], dict]:
    """
    Draw every selected cell and return a *terminal_lookup* dict mapping
    ``(series, parallel)`` to ``{"plus": Vector, "minus": Vector, "cell": dict}``.
    """
    total_s = max(selected_by_series.keys()) if selected_by_series else 1
    terminal_lookup: dict[tuple[int, int], dict] = {}

    for s, row in selected_by_series.items():
        color = (
            get_series_color(s, total_s)
            if cfg["colorize_series"]
            else (0.8, 0.8, 0.8)
        )
        for cell in row:
            draw_selected_cell(
                doc, sketch_obj, cell, radius, rotation,
                series_groups[s], cfg, color,
            )
            plus_pt, minus_pt = _polarity_points(sketch_obj, cell, cfg["polarity_offset"])
            terminal_lookup[(cell["series"], cell["parallel"])] = {
                "plus": plus_pt,
                "minus": minus_pt,
                "cell": cell,
            }

    return terminal_lookup


# ── Polarity position helper ──────────────────────────────────────────────

def _polarity_points(
    sketch_obj,
    cell: dict,
    polarity_offset: float,
) -> tuple[App.Vector, App.Vector]:
    """
    Return global (plus_pt, minus_pt) for *cell*.

    Odd series groups have + facing up (+Y), even groups have + facing down.
    """
    x, y = cell["x"], cell["y"]
    if cell["series"] % 2 == 1:
        plus_local  = (x, y + polarity_offset)
        minus_local = (x, y - polarity_offset)
    else:
        plus_local  = (x, y - polarity_offset)
        minus_local = (x, y + polarity_offset)

    return (
        to_global(sketch_obj, *plus_local,  0),
        to_global(sketch_obj, *minus_local, 0),
    )
