"""
cellpacker.geometry.layers
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Compute per-object-type Z offsets for the Auto-Z 2D layering system.

Every object type gets its own layer index.  The physical offset is
index × step (mm along the sketch normal).  Call build_layers(cfg) to
get a ready-to-use dict that can be merged into cfg or queried directly.
"""

from __future__ import annotations

# Fixed ordering — index = position in the stack (0 = closest to sketch plane).
LAYER_INDICES: dict[str, int] = {
    "layer_z_minus_bus":     0,   # − parallel busbar rails
    "layer_z_minus_markers": 1,   # (−) polarity dots + text
    "layer_z_candidates":    2,   # candidate cell circles
    "layer_z_cells":         3,   # selected cell circles
    "layer_z_cell_labels":   4,   # S/P text on cells
    "layer_z_plus_markers":  5,   # (+) polarity dots + text
    "layer_z_plus_bus":      6,   # + parallel busbar rails
    "layer_z_series":        7,   # series jumper wires
    "layer_z_pack":          8,   # PACK+/PACK− labels
}


def build_layers(cfg: dict) -> dict[str, float]:
    """Return layer-key → mm-offset mapping for the current cfg.

    • Auto-Z ON  : each key = its index × cfg["auto_z_step"]
    • Auto-Z OFF : all keys = 0.0  (everything flat on sketch plane)
    • 3D mode    : layer_z_plus_bus = cell_height, rest = 0.0
    """
    if cfg.get("make_3d"):
        result = {k: 0.0 for k in LAYER_INDICES}
        result["layer_z_plus_bus"] = cfg.get("cell_height", 70.0)
        return result

    if not cfg.get("auto_z", True):
        return {k: 0.0 for k in LAYER_INDICES}

    step = cfg.get("auto_z_step", 1.0)
    return {k: idx * step for k, idx in LAYER_INDICES.items()}
