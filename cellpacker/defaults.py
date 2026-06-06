"""
cellpacker.defaults
~~~~~~~~~~~~~~~~~~~
Single source of truth for all configuration defaults.
The GUI is pre-populated from these values, and they are
used as fallback wherever a key might be missing.
"""

# Standard cylindrical cell presets  {name: (diameter_mm, height_mm)}
# Diameters are nominal; add clearance for wrapper thickness in the dialog.
CELL_PRESETS: dict[str, tuple[float, float]] = {
    "14500": (14.0,  50.0),
    "16340": (16.0,  34.0),
    "18650": (18.4,  65.0),
    "20700": (20.0,  70.0),
    "21700": (21.0,  70.0),
    "26650": (26.0,  65.0),
    "32650": (32.0,  65.0),
    "32700": (32.0,  70.0),
    "4680":  (46.0,  80.0),
}

DEFAULTS: dict = {
    # ── Cell geometry ─────────────────────────────────────────────────────
    "cell_diameter": 21.5,    # mm – physical diameter (incl. wrapper if relevant)
    "clearance": 0.8,         # mm – extra gap between cell surfaces
    "cell_height": 70.0,      # mm – used for 3-D cylinders and Auto-Z

    # ── Pack topology ─────────────────────────────────────────────────────
    "target_s": 20,           # number of series groups
    "target_p": 5,            # cells per parallel group

    # ── Output flags ──────────────────────────────────────────────────────
    "make_2d": True,
    "make_3d": False,
    "make_labels": True,
    "show_candidates": True,       # overlay all candidate cell positions
    "candidates_visible": True,    # whether that overlay is visible on open

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
    "auto_z": True,          # offset layers along sketch normal to match physical heights
    "plus_busbar_z": 70.0,   # distance along sketch normal for + terminal layer
    "minus_busbar_z": 0.0,   # distance along sketch normal for − terminal layer

    # ── Polarity markers ──────────────────────────────────────────────────
    "draw_pack_terminal_labels": True,   # large PACK+ / PACK- markers
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
