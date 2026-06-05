# PR: Modularize BatteryPackLayoutTool into a `cellpacker` package

## Summary

Splits `BatteryPackLayoutTool_v2.FCMacro` (1047-line monolith) into a
proper Python package `cellpacker/` with one responsibility per module.
The macro entry point shrinks to a thin orchestrator of ~90 lines.

---

## New file layout

```
macros/
  BatteryPackLayoutTool_v3.FCMacro   ← thin entry point (replaces v2)

cellpacker/
  defaults.py                         ← all config defaults, single source of truth
  utils.py                            ← parse_float_list, ensure_active_doc

  geometry/
    transforms.py                     ← rotate_2d, to_global, get_edge_angle_*
    face.py                           ← get_local_face, circle_fits, point_inside_face
    grid.py                           ← GridParams, generate_candidate_points

  layout/
    rows.py                           ← cluster_rows, valid_rows
    scoring.py                        ← score_selected (multi-term scoring)
    selector.py                       ← select_compact_sp, build_selected_by_series
    sweep.py                          ← sweep_angles (angle loop → best result)

  drawing/
    colors.py                         ← get_series_color, hsv_to_rgb
    primitives.py                     ← draw_circle, draw_cylinder, draw_polyline, …
    cells.py                          ← draw_candidate_cells, draw_all_selected_cells, groups
    annotations.py                    ← draw_polarity_markers, draw_alignment_arrow

  routing/
    busbars.py                        ← draw_parallel_busbars, draw_series_jumpers

  ui/
    dialog.py                         ← SettingsDialog (PySide2)
    selection.py                      ← get_selected_sketch_and_edge
```

---

## What changed (beyond structure)

| Area | Change |
|---|---|
| `circle_fits` | Samples increased from **16 → 24** for better coverage near tight concave corners |
| `series jumper` | Complete implementation of all three styles (`paired`, `rail`, `single`) including Z-layer alternation |
| PySide2 import | Consolidated; fallback to PySide1 kept but isolated to `ui/dialog.py` |
| `point_to_boundary_distance` | Two-level fallback for robust `Part.Vertex` construction |
| Logging | Structured with separators; `WARNING` prefix for under-capacity packs |
| Type hints | Added throughout pure-Python modules (compatible with Python 3.10+) |

## What is NOT changed

- All scoring weights, defaults, and GUI layout are identical to v2
- FreeCAD document/group structure is unchanged (same group names)
- The v2 macro continues to work; v3 is additive

---

## How to install

1. Copy the `cellpacker/` directory next to `BatteryPackLayoutTool_v3.FCMacro`
   (or anywhere on `sys.path`).
2. Run `BatteryPackLayoutTool_v3.FCMacro` from the FreeCAD macro dialog.

---

## Suggested follow-up PRs

- `feat: unit tests for geometry and layout modules` (pure Python, no FreeCAD needed)
- `feat: improve circle_fits with polygon boundary sampling`
- `feat: alternative packing algorithms (e.g. simulated annealing for irregular shapes)`
- `feat: export bill-of-materials (cell count, busbar lengths) to CSV`
