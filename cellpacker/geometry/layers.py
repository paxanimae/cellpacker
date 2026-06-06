"""
cellpacker.geometry.layers
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Compute per-layer Z offsets for the Auto-Z 2D layering system.

Physical model
--------------
A series battery pack has a TOP FACE and a BOTTOM FACE.  With snake
ordering, cells in adjacent series groups are flipped:

  Odd groups  (S01, S03, …): + terminal faces UP   (top face)
  Even groups (S02, S04, …): + terminal faces DOWN  (bottom face)

Both faces therefore carry a MIX of + and − connections depending on
which series group you are looking at.  It only makes sense to talk
about a "positive side" or "negative side" at the pack's two free end
terminals (PACK+ and PACK−).

Four distinct layers (bottom → top):
  0  layer_z_bottom       bottom-face busbar strips, series jumpers on
                           the bottom face, and bottom-face polarity markers
  1  layer_z_cells         cell circles / cylinders
  2  layer_z_top           top-face busbar strips, series jumpers on the
                           top face, and top-face polarity markers
  3  layer_z_annotations   S/P text labels, PACK+/PACK− labels, arrow

Which face each object belongs to
  Parallel busbar for group S:
    odd S  → + strip at top,    − strip at bottom
    even S → + strip at bottom, − strip at top
  Series jumper S → S+1:
    odd S  → both endpoints at top    face (S's + and S+1's − are both up)
    even S → both endpoints at bottom face (S's + and S+1's − are both down)
  Polarity markers:
    odd S  → (+) at top,    (−) at bottom
    even S → (+) at bottom, (−) at top
"""

from __future__ import annotations

LAYER_INDICES: dict[str, int] = {
    "layer_z_bottom":      0,
    "layer_z_cells":       1,
    "layer_z_top":         2,
    "layer_z_annotations": 3,
}


def build_layers(cfg: dict) -> dict[str, float]:
    """Return layer-key → mm-offset mapping for the current cfg.

    • 2D + Auto-Z ON : each key = its index × cfg["auto_z_step"]
    • 2D + Auto-Z OFF: all keys = 0.0  (everything flat on sketch plane)
    • 3D mode        : bottom = 0, top = cell_height, annotations = cell_height
    """
    if cfg.get("make_3d"):
        ht = cfg.get("cell_height", 70.0)
        return {
            "layer_z_bottom":      0.0,
            "layer_z_cells":       0.0,
            "layer_z_top":         ht,
            "layer_z_annotations": ht,
        }

    if not cfg.get("auto_z", True):
        return {k: 0.0 for k in LAYER_INDICES}

    step = cfg.get("auto_z_step", 1.0)
    return {k: idx * step for k, idx in LAYER_INDICES.items()}
