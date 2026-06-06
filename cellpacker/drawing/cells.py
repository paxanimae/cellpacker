"""
cellpacker.drawing.cells
~~~~~~~~~~~~~~~~~~~~~~~~~
Draw individual cells and manage FreeCAD document groups.
"""

from __future__ import annotations
import FreeCAD as App

from cellpacker.geometry.transforms import to_global
from cellpacker.drawing.primitives import draw_circle, draw_cylinder, draw_text
from cellpacker.drawing.colors import get_series_color


# ── Group helpers ─────────────────────────────────────────────────────────

def make_or_get_group(doc, name: str):
    grp = doc.getObject(name)
    if grp is None:
        grp = doc.addObject("App::DocumentObjectGroup", name)
    return grp


def _try_add(parent, child) -> None:
    try:
        parent.addObject(child)
    except Exception:
        pass


def _delete_tree(doc, name: str) -> None:
    """Recursively delete a named group and all its descendants."""
    grp = doc.getObject(name)
    if grp is None:
        return
    for child in list(getattr(grp, "Group", [])):
        _delete_tree(doc, child.Name)
    try:
        doc.removeObject(name)
    except Exception:
        pass


def get_sketch_normal(sketch_obj) -> App.Vector:
    """
    Return the world-space normal of the sketch plane.
    For a sketch rotated in world space this ensures cell disks
    are drawn flat in the correct plane.
    """
    # The sketch Z axis in local coords is (0,0,1).
    # Transform it to world space via the sketch placement rotation.
    local_z = App.Vector(0, 0, 1)
    return sketch_obj.Placement.Rotation.multVec(local_z)


def build_pack_groups(doc, root_name: str) -> dict[str, object]:
    # Wipe any objects from a previous run with the same name so they
    # don't stack on top of the fresh result.
    _delete_tree(doc, root_name)

    grp_root = make_or_get_group(doc, root_name)
    grp_all  = make_or_get_group(doc, root_name + "_AllCandidates")
    grp_pack = make_or_get_group(doc, root_name + "_Selected")
    grp_bus  = make_or_get_group(doc, root_name + "_Busbars")
    grp_pol  = make_or_get_group(doc, root_name + "_Polarity")
    grp_dir  = make_or_get_group(doc, root_name + "_Direction")

    # Pre-create busbar sub-groups so they appear in the tree in a fixed order.
    grp_bus_plus   = make_or_get_group(doc, root_name + "_Busbars_Plus")
    grp_bus_minus  = make_or_get_group(doc, root_name + "_Busbars_Minus")
    grp_bus_series = make_or_get_group(doc, root_name + "_Busbars_Series")
    for sub in (grp_bus_plus, grp_bus_minus, grp_bus_series):
        _try_add(grp_bus, sub)

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
    series_groups: dict[int, object] = {}
    for s in range(1, total_s + 1):
        sg = make_or_get_group(doc, f"{root_name}_Series_{s:02d}")
        _try_add(parent_group, sg)
        series_groups[s] = sg
    return series_groups


# ── Cell drawing ──────────────────────────────────────────────────────────

def _layer_pt(pt: App.Vector, normal: App.Vector, z: float) -> App.Vector:
    """Offset *pt* by *z* mm along *normal* (the sketch-plane perpendicular)."""
    if z == 0.0:
        return pt
    return App.Vector(pt.x + normal.x * z,
                      pt.y + normal.y * z,
                      pt.z + normal.z * z)


def draw_candidate_cells(
    doc, sketch_obj, points, radius, rotation, group, cfg
) -> None:
    normal  = get_sketch_normal(sketch_obj)
    cell_z  = cfg.get("layer_z_cells", 0.0)
    for i, pt in enumerate(points, start=1):
        gpt = _layer_pt(to_global(sketch_obj, pt[0], pt[1]), normal, cell_z)
        if cfg["make_2d"]:
            draw_circle(doc, gpt, radius, f"CAND_{i:03d}", group,
                        color=(0.70, 0.70, 0.70), normal=normal)
        if cfg["make_3d"]:
            draw_cylinder(doc, gpt, radius, cfg["cell_height"], rotation,
                          f"CAND_{i:03d}_3D", group)


def draw_selected_cell(
    doc, sketch_obj, cell, radius, rotation, group, cfg, color, normal, cell_z
) -> App.Vector:
    gpt  = _layer_pt(to_global(sketch_obj, cell["x"], cell["y"]), normal, cell_z)
    name = f"S{cell['series']:02d}_P{cell['parallel']:02d}"

    if cfg["make_2d"]:
        draw_circle(doc, gpt, radius, name, group, color=color, normal=normal)
    if cfg["make_3d"]:
        draw_cylinder(doc, gpt, radius, cfg["cell_height"], rotation,
                      name + "_3D", group, color=color)
    if cfg["make_labels"]:
        srot = App.Rotation(App.Vector(0, 0, 1), normal)
        draw_text(doc, gpt, f"{cell['series']}/{cell['parallel']}",
                  name + "_TXT", group, color=color, sketch_rotation=srot)
    return gpt


def draw_all_selected_cells(
    doc, sketch_obj, selected_by_series, radius, rotation, series_groups, cfg
) -> dict[tuple[int, int], dict]:
    total_s = max(selected_by_series.keys()) if selected_by_series else 1
    normal  = get_sketch_normal(sketch_obj)
    cell_z  = cfg.get("layer_z_cells", 0.0)
    terminal_lookup: dict[tuple[int, int], dict] = {}

    for s, row in selected_by_series.items():
        color = (
            get_series_color(s, total_s) if cfg["colorize_series"] else (0.8, 0.8, 0.8)
        )
        for cell in row:
            draw_selected_cell(
                doc, sketch_obj, cell, radius, rotation,
                series_groups[s], cfg, color, normal, cell_z,
            )
            plus_pt, minus_pt = _polarity_points(sketch_obj, cell, cfg["polarity_offset"])
            terminal_lookup[(cell["series"], cell["parallel"])] = {
                "plus": plus_pt,
                "minus": minus_pt,
                "cell": cell,
            }

    return terminal_lookup


def _polarity_points(sketch_obj, cell, polarity_offset):
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
