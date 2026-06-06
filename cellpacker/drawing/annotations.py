"""
cellpacker.drawing.annotations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Polarity markers, terminal dots, and the alignment-direction arrow.
"""

from __future__ import annotations
import math
import FreeCAD as App

from cellpacker.geometry.transforms import rotate_2d, to_global
from cellpacker.drawing.primitives import draw_text, draw_circle_outline, draw_polyline


def _offset(pt: App.Vector, normal: App.Vector | None, z: float) -> App.Vector:
    if not normal or z == 0.0:
        return pt
    return App.Vector(pt.x + normal.x * z,
                      pt.y + normal.y * z,
                      pt.z + normal.z * z)


def draw_polarity_markers(
    doc,
    terminal_lookup: dict,
    group,
    cfg: dict,
    sketch_normal: App.Vector | None = None,
) -> None:
    """Draw + / − text labels and optional terminal dots for every cell."""
    label_z = cfg.get("layer_z_labels", 0.0)
    for (s, p), info in terminal_lookup.items():
        name     = f"S{s:02d}_P{p:02d}"
        plus_pt  = _offset(info["plus"],  sketch_normal, label_z)
        minus_pt = _offset(info["minus"], sketch_normal, label_z)

        if cfg["draw_polarity_markers"]:
            draw_text(doc, plus_pt,  "(+)", name + "_PLUS",  group, color=(0.8, 0.0, 0.0))
            draw_text(doc, minus_pt, "(-)", name + "_MINUS", group, color=(0.0, 0.0, 0.8))

        if cfg["draw_terminal_dots"]:
            r = cfg["terminal_dot_radius"]
            draw_circle_outline(doc, plus_pt,  r, name + "_PLUS_DOT",  group, color=(0.9, 0.1, 0.1))
            draw_circle_outline(doc, minus_pt, r, name + "_MINUS_DOT", group, color=(0.1, 0.1, 0.9))


def draw_pack_terminals(
    doc,
    selected_by_series: dict,
    terminal_lookup: dict,
    group,
    cfg: dict,
    sketch_normal: App.Vector,
) -> None:
    """
    Mark the pack-level output terminals:
      PACK-  = unconnected minus rail of the first series group
      PACK+  = unconnected plus rail of the last series group

    Labels and circles are drawn at the centroid of each rail, offset
    along the sketch normal to sit at the correct terminal face height.
    """
    sorted_s  = sorted(selected_by_series.keys())
    s_first   = sorted_s[0]
    s_last    = sorted_s[-1]
    label_z   = cfg.get("layer_z_labels", 0.0)
    dot_r     = cfg.get("terminal_dot_radius", 1.5) * 3.0  # larger circle

    def _rail_centroid(cells, polarity: str) -> App.Vector:
        pts = [terminal_lookup[(c["series"], c["parallel"])][polarity] for c in cells]
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        cz = sum(p.z for p in pts) / len(pts)
        return _offset(App.Vector(cx, cy, cz), sketch_normal, label_z)

    neg_pt = _rail_centroid(selected_by_series[s_first], "minus")
    pos_pt = _rail_centroid(selected_by_series[s_last],  "plus")

    draw_text(doc, neg_pt, "PACK-", "PackTerminal_NEG", group, color=(0.0, 0.0, 1.0))
    draw_text(doc, pos_pt, "PACK+", "PackTerminal_POS", group, color=(1.0, 0.0, 0.0))
    draw_circle_outline(doc, neg_pt, dot_r, "PackTerminal_NEG_ring", group, color=(0.0, 0.0, 1.0))
    draw_circle_outline(doc, pos_pt, dot_r, "PackTerminal_POS_ring", group, color=(1.0, 0.0, 0.0))


def draw_alignment_arrow(
    doc,
    sketch_obj,
    angle_deg: float,
    label: str,
    group,
    length: float,
) -> None:
    """Draw a green arrow indicating the hex-grid alignment direction."""
    # Shaft
    sx, sy = rotate_2d(0.0, 0.0, angle_deg)
    ex, ey = rotate_2d(length, 0.0, angle_deg)
    p1 = to_global(sketch_obj, sx, sy, 0)
    p2 = to_global(sketch_obj, ex, ey, 0)
    draw_polyline(doc, [p1, p2], label + "_shaft", group, color=(0.0, 0.6, 0.0))

    # Arrowhead
    head_len = length * 0.18
    head_ang = 25.0
    vx, vy = ex - sx, ey - sy
    vlen = math.sqrt(vx * vx + vy * vy)
    if vlen > 1e-9:
        ux, uy = vx / vlen, vy / vlen
        for sign in (+head_ang, -head_ang):
            dx, dy = rotate_2d(-head_len * ux, -head_len * uy, sign)
            tip = to_global(sketch_obj, ex + dx, ey + dy, 0)
            draw_polyline(
                doc, [p2, tip],
                f"{label}_head{'L' if sign > 0 else 'R'}",
                group, color=(0.0, 0.6, 0.0),
            )
