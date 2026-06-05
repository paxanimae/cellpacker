"""
cellpacker.defaults
~~~~~~~~~~~~~~~~~~~
Single source of truth for all configuration defaults.
The GUI is pre-populated from these values, and they are
used as fallback wherever a key might be missing.
"""

DEFAULTS: dict = {
    # ── Mode ──────────────────────────────────────────────────────────────
    "mode": "pack",           # "fit" | "pack"

    # ── Cell geometry ─────────────────────────────────────────────────────
    "cell_diameter": 21.5,    # mm – physical diameter (incl. wrapper if relevant)
    "clearance": 0.8,         # mm – extra gap between cell surfaces
    "cell_height": 70.0,      # mm – used for 3-D cylinders only

    # ── Pack topology ─────────────────────────────────────────────────────
    "target_s": 20,           # number of series groups
    "target_p": 5,            # cells per parallel group

    # ── Output flags ──────────────────────────────────────────────────────
    "make_2d": True,
    "make_3d": False,
    "make_labels": True,
    "draw_all_candidates": True,

    # ── Grid alignment ────────────────────────────────────────────────────
    "use_selected_edge_alignment": True,
    "fallback_angle_deg": 0.0,
    "edge_angle_offsets_deg": "0",          # CSV, added to detected edge angle
    "angles_deg": "0,5,10,15,20,25,30",    # CSV, used when edge alignment is off

    # ── Series / parallel visualisation ───────────────────────────────────
    "colorize_series": True,
    "snake_series_order": True,

    # ── Busbar / routing ──────────────────────────────────────────────────
    "draw_parallel_busbars": True,
    "draw_series_jumpers": True,
    "series_jumper_style": "paired",        # "single" | "paired" | "rail"
    "draw_busbar_solids": False,
    "busbar_width": 8.0,
    "busbar_thickness": 0.2,
    # Z height of the positive-terminal busbar layer (top face of cells).
    # Should match cell_height.  Negative-terminal layer sits at the base.
    "plus_busbar_z": 70.0,
    "minus_busbar_z": 0.0,

    # ── Polarity markers ──────────────────────────────────────────────────
    "draw_polarity_markers": True,
    "polarity_offset": 6.0,
    "draw_terminal_dots": True,
    "terminal_dot_radius": 1.5,

    # ── Alignment arrow ───────────────────────────────────────────────────
    "draw_alignment_arrow": True,
    "alignment_arrow_length": 60.0,

    # ── Scoring weights ───────────────────────────────────────────────────
    "prefer_shape_usage": True,
    "shape_usage_weight": 2.5,
    "compactness_weight": 1.0,
    "center_bias_weight": 1.0,
    "row_shift_weight": 2.5,
    "boundary_margin_penalty_weight": 0.25,

    # ── Visual style (not exposed in GUI, but overridable in code) ────────
    "plus_busbar_color":  (0.85, 0.10, 0.10),   # red  – positive layer
    "minus_busbar_color": (0.10, 0.10, 0.85),   # blue – negative layer
    "cell_fill_transparency": 0,
}
