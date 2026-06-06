"""
cellpacker.defaults
~~~~~~~~~~~~~~~~~~~
Single source of truth for all configuration defaults.
The GUI is pre-populated from these values, and they are
used as fallback wherever a key might be missing.
"""

# Standard cylindrical cell presets  {name: (diameter_mm, height_mm)}
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
    "cell_diameter": 21.5,
    "clearance": 0.8,
    "cell_height": 70.0,        # 3D only: cylinder height

    # ── Pack topology ─────────────────────────────────────────────────────
    "target_s": 20,
    "target_p": 5,

    # ── Output mode ───────────────────────────────────────────────────────
    # make_2d / make_3d are mutually exclusive and set by the dialog.
    "make_2d": True,
    "make_3d": False,
    "make_labels": True,
    "show_candidates": True,
    "candidates_visible": True,

    # ── Z-layer offsets along the sketch normal ───────────────────────────
    # 2D + Auto-Z ON : small values (mm) that visually separate flat layers.
    # 2D + Auto-Z OFF: all zero — every object on the sketch plane.
    # 3D             : layer_z_plus = cell_height, rest = 0 (set by dialog).
    # Auto-Z separates objects by which physical face they belong to.
    # Four layers (bottom → top), each = index × auto_z_step:
    #   0  layer_z_bottom       bottom-face strips, jumpers, and markers
    #   1  layer_z_cells        cell circles / cylinders
    #   2  layer_z_top          top-face strips, jumpers, and markers
    #   3  layer_z_annotations  S/P labels, PACK+/PACK−, arrow
    # Which face an object belongs to is determined by series group parity:
    #   odd groups  → + terminal at top face, − terminal at bottom face
    #   even groups → + terminal at bottom face, − terminal at top face
    "auto_z": True,
    "auto_z_step": 1.0,

    # ── Grid alignment ────────────────────────────────────────────────────
    "use_selected_edge_alignment": True,
    "fallback_angle_deg": 0.0,
    "edge_angle_offsets_deg": "0",
    "angles_deg": "0,5,10,15,20,25,30",

    # ── Series / parallel visualisation ───────────────────────────────────
    "colorize_series": True,
    "snake_series_order": True,

    # ── Busbar / routing ──────────────────────────────────────────────────
    "draw_parallel_busbars": True,
    "draw_series_jumpers": True,
    "series_jumper_style": "paired",
    "draw_busbar_solids": False,    # 3D only
    "busbar_width": 8.0,
    "busbar_thickness": 0.2,        # 3D only

    # ── Polarity markers ──────────────────────────────────────────────────
    "draw_pack_terminal_labels": True,
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

    # ── Visual style ──────────────────────────────────────────────────────
    "plus_busbar_color":  (0.85, 0.10, 0.10),
    "minus_busbar_color": (0.10, 0.10, 0.85),
    "cell_fill_transparency": 0,
}
