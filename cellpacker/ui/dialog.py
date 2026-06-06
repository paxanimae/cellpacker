"""
cellpacker.ui.dialog
~~~~~~~~~~~~~~~~~~~~~
PySide2/6 settings dialog.  Returns a cfg dict on acceptance or ``None``
on cancellation.
"""

from __future__ import annotations

from cellpacker.defaults import DEFAULTS, CELL_PRESETS


def get_user_settings(
    defaults: dict = DEFAULTS,
    preview_fn=None,
    cleanup_fn=None,
) -> dict | None:
    """
    Show the settings dialog and return the chosen configuration dict,
    or ``None`` if the user cancelled.

    *preview_fn(cfg)*  – called when the user clicks Preview.
    *cleanup_fn()*     – called when the user cancels.
    """
    try:
        from PySide2 import QtWidgets as Qt, QtCore  # noqa: F401
    except ImportError:
        from PySide import QtGui as Qt  # type: ignore

    class SettingsDialog(Qt.QDialog):
        def __init__(self, defs: dict) -> None:
            super().__init__()
            self.setWindowTitle("Battery Pack Layout Tool")
            self.resize(820, 700)
            self._defs = defs

            root = Qt.QVBoxLayout(self)
            tabs = Qt.QTabWidget()
            root.addWidget(tabs)

            tabs.addTab(self._make_help_tab(),    "Help")
            tabs.addTab(self._make_pack_tab(),    "Pack")
            tabs.addTab(self._make_display_tab(), "Display")
            tabs.addTab(self._make_routing_tab(), "Routing")
            tabs.addTab(self._make_align_tab(),   "Alignment")
            tabs.addTab(self._make_score_tab(),   "Scoring")

            # All tabs are built — wire up cross-tab mode cascade.
            self.make_2d.toggled.connect(self._on_output_mode)
            self._on_output_mode()          # apply initial state

            btns = Qt.QDialogButtonBox(
                Qt.QDialogButtonBox.Ok | Qt.QDialogButtonBox.Cancel
            )
            btns.accepted.connect(self.accept)
            btns.rejected.connect(self.reject)

            if preview_fn is not None:
                prev = btns.addButton("Preview", Qt.QDialogButtonBox.ActionRole)
                prev.setToolTip(
                    "Run the layout with the current settings and draw it into\n"
                    "the FreeCAD viewport — without closing this dialog.\n"
                    "Adjust settings and click Preview again to update."
                )
                prev.clicked.connect(lambda: preview_fn(self.values()))

            root.addWidget(btns)

        # ── Widget helpers ────────────────────────────────────────────────

        @staticmethod
        def _row(form, label_text: str, widget, tip: str):
            """Add a labelled row with the same tooltip on both label and widget."""
            widget.setToolTip(tip)
            lbl = Qt.QLabel(label_text)
            lbl.setToolTip(tip)
            form.addRow(lbl, widget)

        @staticmethod
        def _dspin(val, lo, hi, decimals=3):
            sb = Qt.QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setDecimals(decimals)
            sb.setValue(float(val))
            return sb

        @staticmethod
        def _spin(val, lo, hi):
            sb = Qt.QSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(int(val))
            return sb

        @staticmethod
        def _check(val):
            cb = Qt.QCheckBox()
            cb.setChecked(bool(val))
            return cb

        @staticmethod
        def _head(text):
            lbl = Qt.QLabel(f"<b>{text}</b>")
            return lbl

        # ── Tab: Help ─────────────────────────────────────────────────────

        def _make_help_tab(self):
            w = Qt.QWidget()
            lay = Qt.QVBoxLayout(w)
            te = Qt.QTextEdit()
            te.setReadOnly(True)
            te.setHtml("""
<h2>Battery Pack Layout Tool</h2>
<p><b>1.</b> Draw a closed sketch for the pack outline. Select it
(Ctrl-select a straight edge to align the grid to it), then run this macro.</p>
<p><b>2.</b> Set the cell type, series (S) and parallel (P) count in the
<b>Pack</b> tab.</p>
<p><b>3.</b> Choose what to render in the <b>Display</b> tab.
Turn on <i>Auto-Z</i> to separate busbar layers by their physical height
(minus terminal at the base, plus terminal at the top).</p>
<p><b>4.</b> Configure busbars in the <b>Routing</b> tab. Uncheck a group
header to disable that busbar type entirely.</p>
<p><b>5.</b> Click <b>Preview</b> to draw into the viewport without closing
the dialog. Adjust and preview as many times as you like, then click
<b>OK</b> to finalise. <b>Cancel</b> removes any preview from the document.</p>
<pre>
  Candidates:          Selected 5s5p:         Busbars:
   o o o o o           S01: + + + + +         ─── parallel rail (+ face)
    o o o o             S02: - - - - -         ─── parallel rail (- face)
   o o o o o           S03: + + + + +         ╱   series jumpers
</pre>
""")
            lay.addWidget(te)
            return w

        # ── Tab: Pack ─────────────────────────────────────────────────────

        def _make_pack_tab(self):
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            f.addRow(self._head("Cell dimensions"))

            self.cell_type = Qt.QComboBox()
            self.cell_type.addItem("Custom")
            for name in CELL_PRESETS:
                self.cell_type.addItem(name)
            self._row(f, "Cell type", self.cell_type,
                "Standard cylindrical cell formats.\n"
                "Selecting one fills in diameter and height automatically.\n"
                "18650 = 18.4 mm × 65 mm  |  21700 = 21 mm × 70 mm  |  etc.\n"
                "Choose 'Custom' to enter your own values.")

            self.cell_diameter = self._dspin(d["cell_diameter"], 1.0, 100.0)
            self._row(f, "Cell diameter (mm)", self.cell_diameter,
                "Outer diameter of the cell including any shrink-wrap sleeve.\n"
                "Add a little extra if the cells are a tight fit in your enclosure.")

            self.clearance = self._dspin(d["clearance"], 0.0, 20.0)
            self._row(f, "Clearance (mm)", self.clearance,
                "Minimum air gap between adjacent cells.\n"
                "Pitch = diameter + clearance.\n"
                "Increase for airflow, glue, or structural material between cells.")

            self.cell_height = self._dspin(d["cell_height"], 1.0, 200.0)
            self._row(f, "Cell height (mm)", self.cell_height,
                "Total height of the cell from base to top cap.\n"
                "Used for 3D cylinders and, when Auto-Z is on, sets the\n"
                "height of the positive-terminal busbar layer automatically.")

            f.addRow(Qt.QLabel(""))
            f.addRow(self._head("Pack topology"))

            self.target_s = self._spin(d["target_s"], 1, 200)
            self._row(f, "Series groups (S)", self.target_s,
                "Number of series-connected cell groups.\n"
                "More series groups = higher pack voltage.\n"
                "Example: 20S Li-ion ≈ 72 V nominal.")

            self.target_p = self._spin(d["target_p"], 1, 100)
            self._row(f, "Parallel cells (P)", self.target_p,
                "Number of cells in each parallel group.\n"
                "More parallel cells = higher capacity (Ah).\n"
                "Example: 5P × 3 Ah cells = 15 Ah total.")

            f.addRow(Qt.QLabel(""))
            f.addRow(self._head("Series layout"))

            self.colorize_series = self._check(d["colorize_series"])
            self._row(f, "Colorize by series group", self.colorize_series,
                "Give each series group a unique colour so you can visually\n"
                "trace series connections across the pack.")

            self.snake = self._check(d["snake_series_order"])
            self._row(f, "Snake series order", self.snake,
                "Alternate the wiring direction of each series group:\n"
                "group 1 goes left → right, group 2 right → left, and so on.\n"
                "This minimises the length of the jumper wires between groups\n"
                "because each group connects to the one directly next to it.")

            # ── Preset logic ──────────────────────────────────────────────
            def _apply_preset(_idx):
                name = self.cell_type.currentText()
                if name in CELL_PRESETS:
                    diam, ht = CELL_PRESETS[name]
                    self.cell_diameter.setValue(diam)
                    self.cell_height.setValue(ht)

            self.cell_type.currentIndexChanged.connect(_apply_preset)

            for name, (diam, ht) in CELL_PRESETS.items():
                if (abs(d["cell_diameter"] - diam) < 0.05
                        and abs(d["cell_height"] - ht) < 0.05):
                    self.cell_type.setCurrentText(name)
                    break

            return w

        # ── Tab: Display ──────────────────────────────────────────────────

        def _make_display_tab(self):
            d = self._defs
            w = Qt.QWidget()
            scroll = Qt.QScrollArea()
            scroll.setWidgetResizable(True)
            inner = Qt.QWidget()
            f = Qt.QFormLayout(inner)

            # ── Output mode ───────────────────────────────────────────────
            f.addRow(self._head("Output mode"))

            render_w = Qt.QWidget()
            render_lay = Qt.QHBoxLayout(render_w)
            render_lay.setContentsMargins(0, 0, 0, 0)
            self.make_2d = Qt.QRadioButton("2D — flat layout")
            self.make_3d = Qt.QRadioButton("3D — physical model")
            self._render_grp = Qt.QButtonGroup(render_w)
            self._render_grp.addButton(self.make_2d)
            self._render_grp.addButton(self.make_3d)
            (self.make_3d if d.get("make_3d") else self.make_2d).setChecked(True)
            tip_2d = (
                "Everything is drawn flat on the sketch plane at Z = 0:\n"
                "  • Cells → filled circles\n"
                "  • Busbars → flat polylines or strips\n"
                "  • Labels → flat text\n"
                "Z-layering, Auto-Z, and busbar thickness do not apply in 2D mode.")
            tip_3d = (
                "Everything is drawn with physical height above the sketch plane:\n"
                "  • Cells → solid cylinders (cell height)\n"
                "  • Busbars → solid strips at the correct terminal-face height\n"
                "  • Auto-Z places each layer at its real physical position.")
            self.make_2d.setToolTip(tip_2d)
            self.make_3d.setToolTip(tip_3d)
            render_lay.addWidget(self.make_2d)
            render_lay.addWidget(self.make_3d)

            lbl = Qt.QLabel("Output mode")
            lbl.setToolTip("Controls the entire output — cells, busbars, and labels.\n"
                           "2D: flat sketch-plane layout.  3D: physical model with height.")
            f.addRow(lbl, render_w)

            self.make_labels = self._check(d["make_labels"])
            self._row(f, "Draw S/P labels on cells", self.make_labels,
                "Print the series/parallel index on each cell (e.g. S03/P2).\n"
                "Helps when manually wiring a pack — you can see exactly which\n"
                "cell belongs to which series group and parallel position.")

            # ── Candidate overlay ─────────────────────────────────────────
            f.addRow(Qt.QLabel(""))
            f.addRow(self._head("Candidate cell overlay"))

            self.show_candidates = self._check(d.get("show_candidates", True))
            self._row(f, "Show all candidate positions", self.show_candidates,
                "Draw a grey circle for every position where a cell could fit\n"
                "inside the outline — not just the selected pack cells.\n"
                "Useful for checking packing density and unused space.")

            self.candidates_visible = self._check(d.get("candidates_visible", True))
            self._row(f, "  Initially visible", self.candidates_visible,
                "Whether the candidate overlay is shown when the macro finishes.\n"
                "You can toggle it later in the model tree without re-running.")

            self.show_candidates.stateChanged.connect(
                lambda s: self.candidates_visible.setEnabled(bool(s))
            )
            self.candidates_visible.setEnabled(self.show_candidates.isChecked())

            # ── Annotations ───────────────────────────────────────────────
            f.addRow(Qt.QLabel(""))
            f.addRow(self._head("Annotations"))

            self.draw_pol = self._check(d["draw_polarity_markers"])
            self._row(f, "Draw (+) / (−) markers per cell", self.draw_pol,
                "Place a small (+) or (−) label at each cell's positive and\n"
                "negative terminal position.\n"
                "Odd series groups have + at the top, even groups have + at the bottom\n"
                "(alternating polarity convention for series-wired packs).")

            self.draw_dots = self._check(d["draw_terminal_dots"])
            self._row(f, "Draw terminal dots", self.draw_dots,
                "Draw a small circle at each terminal position to mark the\n"
                "exact point where a busbar or wire connects.")

            self.dot_radius = self._dspin(d["terminal_dot_radius"], 0.1, 20.0)
            self._row(f, "  Terminal dot radius (mm)", self.dot_radius,
                "Radius of the terminal dot circles in mm.")

            self.pol_offset = self._dspin(d["polarity_offset"], 0.1, 50.0)
            self._row(f, "  Polarity offset from centre (mm)", self.pol_offset,
                "How far the (+)/(−) marker is placed from the cell centre.\n"
                "Set this to just above the cell radius so markers appear\n"
                "at the terminal face rather than inside the cell body.")

            self.draw_pack_labels = self._check(d.get("draw_pack_terminal_labels", True))
            self._row(f, "Draw PACK+ / PACK− output labels", self.draw_pack_labels,
                "Mark the two output terminals of the whole battery pack:\n"
                "  PACK−  = the free negative rail of the first series group\n"
                "  PACK+  = the free positive rail of the last series group\n"
                "These are the points you connect your load or BMS to.")

            self.draw_arrow = self._check(d["draw_alignment_arrow"])
            self._row(f, "Draw grid alignment arrow", self.draw_arrow,
                "Draw an arrow showing the direction the hex grid is aligned to.\n"
                "Useful for verifying that edge alignment worked correctly.")

            self.arrow_length = self._dspin(d["alignment_arrow_length"], 1.0, 1000.0)
            self._row(f, "  Arrow length (mm)", self.arrow_length,
                "Length of the alignment direction arrow in mm.")

            # ── Auto-Z (2D mode only) ─────────────────────────────────────
            f.addRow(Qt.QLabel(""))

            self.auto_z_grp = Qt.QGroupBox("Auto-Z layer separation  (2D mode only)")
            self.auto_z_grp.setCheckable(True)
            self.auto_z_grp.setChecked(d.get("auto_z", True))
            self.auto_z_grp.setToolTip(
                "In 2D mode all objects are flat, so they stack on top of each other\n"
                "in the viewport. Auto-Z pushes each layer a few mm along the sketch\n"
                "normal so you can see them separately — like CSS z-index but in 3D space.\n\n"
                "The values below are small offsets (mm) along the sketch normal axis\n"
                "(perpendicular to the sketch plane). They do NOT represent physical height.\n\n"
                "Uncheck to draw everything on the sketch plane (all at offset = 0).")
            az = Qt.QFormLayout(self.auto_z_grp)

            self.layer_z_minus = self._dspin(d.get("layer_z_minus", 0.0), -100.0, 100.0, 1)
            self._row(az, "− layer offset (mm)", self.layer_z_minus,
                "Offset for: minus busbar rail, (−) polarity markers, PACK− label.\n"
                "Typically 0 — the bottom-most layer, sitting on the sketch plane.")

            self.layer_z_cells = self._dspin(d.get("layer_z_cells", 1.0), -100.0, 100.0, 1)
            self._row(az, "Cell layer offset (mm)", self.layer_z_cells,
                "Offset for: cell circles, candidate circles, S/P text labels.\n"
                "Should sit between the minus and plus layers.")

            self.layer_z_plus = self._dspin(d.get("layer_z_plus", 2.0), -100.0, 100.0, 1)
            self._row(az, "+ layer offset (mm)", self.layer_z_plus,
                "Offset for: plus busbar rail, (+) polarity markers, PACK+ label.\n"
                "Typically the top-most layer.")

            f.addRow(self.auto_z_grp)

            scroll.setWidget(inner)
            outer = Qt.QVBoxLayout(w)
            outer.addWidget(scroll)
            return w

        def _on_output_mode(self):
            """Cascade 2D/3D mode — enable/disable all mode-specific widgets."""
            is_3d = self.make_3d.isChecked()
            # Cell height only meaningful in 3D (cylinder height)
            self.cell_height.setEnabled(is_3d)
            # Auto-Z is a 2D-only concept
            self.auto_z_grp.setEnabled(not is_3d)
            # Routing: solid strips and thickness only exist in 3D
            self.busbar_solids.setEnabled(is_3d)
            self.busbar_thickness.setEnabled(is_3d)

        # ── Tab: Routing ──────────────────────────────────────────────────

        def _make_routing_tab(self):
            d = self._defs
            w = Qt.QWidget()
            lay = Qt.QVBoxLayout(w)

            # ── Parallel busbars ──────────────────────────────────────────
            self.grp_par = Qt.QGroupBox("Parallel busbars")
            self.grp_par.setCheckable(True)
            self.grp_par.setChecked(d["draw_parallel_busbars"])
            self.grp_par.setToolTip(
                "Busbars that connect cells within the same series group in parallel.\n"
                "There is one busbar on the positive-terminal face and one on\n"
                "the negative-terminal face of each series group.\n"
                "Uncheck this box to skip drawing parallel busbars entirely.")
            fpar = Qt.QFormLayout(self.grp_par)

            self.busbar_solids = self._check(d["draw_busbar_solids"])
            self._row(fpar, "Draw as solid strips", self.busbar_solids,
                "Create solid 3D rectangular strips for each busbar segment\n"
                "instead of simple wire lines.\n"
                "More physically accurate but slower to generate.\n"
                "Solid strip dimensions are controlled by Width and Thickness below.")

            self.busbar_width = self._dspin(d["busbar_width"], 0.1, 100.0)
            self._row(fpar, "Width (mm)", self.busbar_width,
                "Physical width of the busbar strip in mm.\n"
                "For nickel strip this is typically 6–10 mm.\n"
                "In wire mode this also scales the line thickness in the viewport.")

            self.busbar_thickness = self._dspin(d["busbar_thickness"], 0.01, 20.0)
            self._row(fpar, "Thickness (mm)", self.busbar_thickness,
                "Thickness of the solid busbar strip in mm.\n"
                "For pure nickel strip: 0.1–0.3 mm.  For copper strip: 0.1–0.5 mm.\n"
                "Only used when 'Draw as solid strips' is enabled.")
            lay.addWidget(self.grp_par)

            # ── Series jumpers ────────────────────────────────────────────
            self.grp_ser = Qt.QGroupBox("Series jumpers")
            self.grp_ser.setCheckable(True)
            self.grp_ser.setChecked(d["draw_series_jumpers"])
            self.grp_ser.setToolTip(
                "Busbars that connect the positive rail of one series group to\n"
                "the negative rail of the next group, forming the series chain.\n"
                "These carry the full pack current and run between terminal faces.\n"
                "Uncheck this box to skip drawing series jumpers entirely.")
            fser = Qt.QFormLayout(self.grp_ser)

            self.jumper_style = Qt.QComboBox()
            self.jumper_style.addItems(["paired", "rail", "single"])
            self.jumper_style.setCurrentText(str(d.get("series_jumper_style", "paired")))
            self._row(fser, "Jumper style", self.jumper_style,
                "How series jumpers are drawn between adjacent groups:\n\n"
                "  paired  – One jumper per parallel cell. The leftmost cell of\n"
                "            group S connects to the leftmost of group S+1, etc.\n"
                "            Most realistic for nickel-strip packs.\n\n"
                "  rail    – A single jumper between the nearest endpoints of\n"
                "            the two parallel rails. Simplest representation.\n\n"
                "  single  – One jumper from any terminal of group S to any\n"
                "            terminal of group S+1 (legacy, least accurate).")
            lay.addWidget(self.grp_ser)

            lay.addStretch()
            return w

        # ── Tab: Alignment ────────────────────────────────────────────────

        def _make_align_tab(self):
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            self.use_edge_align = self._check(d["use_selected_edge_alignment"])
            self._row(f, "Align grid to selected edge", self.use_edge_align,
                "Use the angle of the Ctrl-selected edge to align the hex grid.\n"
                "Select a frame tube, wall, or any straight edge before running\n"
                "the macro to make the cell rows run parallel to it.\n"
                "If no edge is selected, the fallback angle is used instead.")

            self.fallback_angle = self._dspin(d["fallback_angle_deg"], -360.0, 360.0)
            self._row(f, "Fallback angle (deg)", self.fallback_angle,
                "Grid angle to use when no edge is selected or edge alignment\n"
                "is disabled. 0° = rows run horizontally.")

            self.edge_offsets = Qt.QLineEdit(str(d["edge_angle_offsets_deg"]))
            self._row(f, "Edge angle offsets (deg, CSV)", self.edge_offsets,
                "Comma-separated list of angle offsets to try relative to the\n"
                "detected edge angle. The layout is computed for each offset\n"
                "and the best result is kept.\n"
                "Example: '0, 5, -5' tries the edge angle ± 5 degrees.")

            self.angles = Qt.QLineEdit(str(d["angles_deg"]))
            self._row(f, "Angle sweep (deg, CSV)", self.angles,
                "Comma-separated list of absolute grid angles to try when edge\n"
                "alignment is disabled. The best-scoring result is kept.\n"
                "More angles = better chance of a good fit, but slower.")

            return w

        # ── Tab: Scoring ──────────────────────────────────────────────────

        def _make_score_tab(self):
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            f.addRow(Qt.QLabel(
                "Scoring weights control how the algorithm chooses between\n"
                "candidate layouts when several equally-sized windows exist.\n"
                "Higher weight = that criterion matters more."
            ))
            f.addRow(Qt.QLabel(""))

            self.prefer_usage = self._check(d["prefer_shape_usage"])
            self._row(f, "Prefer shape usage", self.prefer_usage,
                "When ON, the scorer strongly rewards layouts that fill more\n"
                "of the outline area, even if the pack is less compact.\n"
                "Turn OFF to let the other weights decide.")

            self.w_usage = self._dspin(d["shape_usage_weight"], 0.0, 50.0)
            self._row(f, "Shape usage weight", self.w_usage,
                "How much to reward using a larger fraction of the outline area.\n"
                "Increase to pack cells closer to the boundary.")

            self.w_compact = self._dspin(d["compactness_weight"], 0.0, 50.0)
            self._row(f, "Compactness weight", self.w_compact,
                "How much to reward packs where selected cells are clustered\n"
                "together with minimal internal gaps.")

            self.w_center = self._dspin(d["center_bias_weight"], 0.0, 50.0)
            self._row(f, "Center bias weight", self.w_center,
                "How much to reward packs whose centre of mass is close to\n"
                "the centre of the outline. Useful for symmetric shapes.")

            self.w_rowshift = self._dspin(d["row_shift_weight"], 0.0, 50.0)
            self._row(f, "Row shift weight", self.w_rowshift,
                "Penalty for large X-offset differences between adjacent series\n"
                "rows. Higher values encourage straighter, more rectangular packs\n"
                "where series jumper wires are all roughly the same length.")

            self.w_boundary = self._dspin(d["boundary_margin_penalty_weight"], 0.0, 50.0)
            self._row(f, "Boundary margin penalty weight", self.w_boundary,
                "Penalty for cells that sit very close to the outline boundary.\n"
                "Increase to keep cells away from the edge (e.g. for wall clearance).")

            return w

        # ── Result extraction ─────────────────────────────────────────────

        def values(self) -> dict:
            d    = self._defs
            is_3d = self.make_3d.isChecked()
            auto_z = (not is_3d) and self.auto_z_grp.isChecked()
            return {
                "cell_diameter":                 self.cell_diameter.value(),
                "clearance":                     self.clearance.value(),
                "cell_height":                   self.cell_height.value(),
                "target_s":                      self.target_s.value(),
                "target_p":                      self.target_p.value(),
                "colorize_series":               self.colorize_series.isChecked(),
                "snake_series_order":            self.snake.isChecked(),
                "make_2d":                       not is_3d,
                "make_3d":                       is_3d,
                "make_labels":                   self.make_labels.isChecked(),
                "show_candidates":               self.show_candidates.isChecked(),
                "candidates_visible":            self.candidates_visible.isChecked(),
                "draw_polarity_markers":         self.draw_pol.isChecked(),
                "polarity_offset":               self.pol_offset.value(),
                "draw_terminal_dots":            self.draw_dots.isChecked(),
                "terminal_dot_radius":           self.dot_radius.value(),
                "draw_pack_terminal_labels":     self.draw_pack_labels.isChecked(),
                "draw_alignment_arrow":          self.draw_arrow.isChecked(),
                "alignment_arrow_length":        self.arrow_length.value(),
                # Z-layer offsets: small visual offsets in 2D, physical in 3D
                "auto_z":        auto_z,
                "layer_z_minus": self.layer_z_minus.value() if auto_z else 0.0,
                "layer_z_cells": self.layer_z_cells.value() if auto_z else 0.0,
                "layer_z_plus":  (self.layer_z_plus.value() if auto_z
                                  else (self.cell_height.value() if is_3d else 0.0)),
                # Routing
                "draw_parallel_busbars":         self.grp_par.isChecked(),
                "draw_busbar_solids":            is_3d and self.busbar_solids.isChecked(),
                "busbar_width":                  self.busbar_width.value(),
                "busbar_thickness":              self.busbar_thickness.value() if is_3d else 0.0,
                "draw_series_jumpers":           self.grp_ser.isChecked(),
                "series_jumper_style":           self.jumper_style.currentText(),
                # Alignment
                "use_selected_edge_alignment":   self.use_edge_align.isChecked(),
                "fallback_angle_deg":            self.fallback_angle.value(),
                "edge_angle_offsets_deg":        self.edge_offsets.text(),
                "angles_deg":                    self.angles.text(),
                # Scoring
                "prefer_shape_usage":            self.prefer_usage.isChecked(),
                "shape_usage_weight":            self.w_usage.value(),
                "compactness_weight":            self.w_compact.value(),
                "center_bias_weight":            self.w_center.value(),
                "row_shift_weight":              self.w_rowshift.value(),
                "boundary_margin_penalty_weight": self.w_boundary.value(),
                # Passthrough
                "plus_busbar_color":             d["plus_busbar_color"],
                "minus_busbar_color":            d["minus_busbar_color"],
                "cell_fill_transparency":        d["cell_fill_transparency"],
            }

        def reject(self):
            if cleanup_fn is not None:
                cleanup_fn()
            super().reject()

    dlg = SettingsDialog(defaults)
    if dlg.exec_():
        return dlg.values()
    return None
