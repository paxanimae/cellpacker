"""
cellpacker.ui.dialog
~~~~~~~~~~~~~~~~~~~~~
PySide2 settings dialog.  Returns a cfg dict on acceptance or ``None``
on cancellation.
"""

from __future__ import annotations

from cellpacker.defaults import DEFAULTS


def get_user_settings(defaults: dict = DEFAULTS) -> dict | None:
    """
    Show the settings dialog and return the chosen configuration dict,
    or ``None`` if the user cancelled.
    """
    try:
        from PySide2 import QtWidgets as Qt, QtCore  # noqa: F401
    except ImportError:
        from PySide import QtGui as Qt  # type: ignore

    class SettingsDialog(Qt.QDialog):
        def __init__(self, defs: dict) -> None:
            super().__init__()
            self.setWindowTitle("Battery Pack Layout Tool")
            self.resize(780, 720)
            self._defs = defs

            root = Qt.QVBoxLayout(self)
            tabs = Qt.QTabWidget()
            root.addWidget(tabs)

            tabs.addTab(self._make_help_tab(),    "Help")
            tabs.addTab(self._make_general_tab(), "General")
            tabs.addTab(self._make_align_tab(),   "Alignment")
            tabs.addTab(self._make_route_tab(),   "Routing")
            tabs.addTab(self._make_score_tab(),   "Scoring")

            btns = Qt.QDialogButtonBox(
                Qt.QDialogButtonBox.Ok | Qt.QDialogButtonBox.Cancel
            )
            btns.accepted.connect(self.accept)
            btns.rejected.connect(self.reject)
            root.addWidget(btns)

        # ── Tab builders ──────────────────────────────────────────────────

        def _make_help_tab(self) -> Qt.QWidget:
            w = Qt.QWidget()
            lay = Qt.QVBoxLayout(w)
            te = Qt.QTextEdit()
            te.setReadOnly(True)
            te.setHtml("""
<h2>Battery Pack Layout Tool</h2>
<p><b>1.</b> Draw or import a closed sketch representing the usable pack
outline.</p>
<p><b>2.</b> Select the closed sketch. To align rows to a frame tube or
edge, also Ctrl-select one straight edge before running the macro.</p>
<p><b>3.</b> Choose <b>Mode = pack</b> for a full S/P layout with labels,
polarity and busbars. Choose <b>Mode = fit</b> to preview the maximum
number of cells that can fit.</p>
<p><b>4.</b> Pitch = diameter + clearance. For 21700 cells, 21.0–21.5 mm
diameter and 0.5–1.0 mm clearance is typical.</p>
<p><b>5.</b> Set <b>Series groups (S)</b> and <b>Parallel cells (P)</b>.
Example: 20s4p = 20 groups × 4 cells = 80 cells total.</p>
<pre>
Candidate cells:      Selected 20s4p:       Busbars:
 o o o o o            S01: + + + +          — parallel rails within group
  o o o o              S02: - - - -          | series jumpers between groups
 o o o o o            S03: + + + +
</pre>
""")
            lay.addWidget(te)
            return w

        def _make_general_tab(self) -> Qt.QWidget:
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            self.mode = Qt.QComboBox()
            self.mode.addItems(["fit", "pack"])
            self.mode.setCurrentText(str(d["mode"]))
            f.addRow("Mode", self.mode)

            self.cell_diameter = self._dspin(d["cell_diameter"], 1.0, 100.0)
            f.addRow("Cell diameter (mm)", self.cell_diameter)

            self.clearance = self._dspin(d["clearance"], 0.0, 20.0)
            f.addRow("Clearance (mm)", self.clearance)

            self.cell_height = self._dspin(d["cell_height"], 1.0, 200.0)
            f.addRow("Cell height (mm)", self.cell_height)

            self.target_s = self._spin(d["target_s"], 1, 200)
            f.addRow("Series groups (S)", self.target_s)

            self.target_p = self._spin(d["target_p"], 1, 100)
            f.addRow("Parallel cells (P)", self.target_p)

            self.make_2d = self._check(d["make_2d"])
            f.addRow("Draw 2D cells", self.make_2d)

            self.make_3d = self._check(d["make_3d"])
            f.addRow("Draw 3D cells", self.make_3d)

            self.make_labels = self._check(d["make_labels"])
            f.addRow("Draw S/P labels", self.make_labels)

            self.draw_all_candidates = self._check(d["draw_all_candidates"])
            f.addRow("Draw all candidate cells", self.draw_all_candidates)

            return w

        def _make_align_tab(self) -> Qt.QWidget:
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            self.use_edge_align = self._check(d["use_selected_edge_alignment"])
            f.addRow("Use selected edge alignment", self.use_edge_align)

            self.fallback_angle = self._dspin(d["fallback_angle_deg"], -360.0, 360.0)
            f.addRow("Fallback angle (deg)", self.fallback_angle)

            self.edge_offsets = Qt.QLineEdit(str(d["edge_angle_offsets_deg"]))
            f.addRow("Edge angle offsets (deg, CSV)", self.edge_offsets)

            self.angles = Qt.QLineEdit(str(d["angles_deg"]))
            f.addRow("Angle sweep (deg, CSV)", self.angles)

            self.draw_arrow = self._check(d["draw_alignment_arrow"])
            f.addRow("Draw alignment arrow", self.draw_arrow)

            self.arrow_length = self._dspin(d["alignment_arrow_length"], 1.0, 1000.0)
            f.addRow("Alignment arrow length", self.arrow_length)

            return w

        def _make_route_tab(self) -> Qt.QWidget:
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            self.colorize_series = self._check(d["colorize_series"])
            f.addRow("Colorize series", self.colorize_series)

            self.snake = self._check(d["snake_series_order"])
            f.addRow("Snake series order", self.snake)

            self.draw_par = self._check(d["draw_parallel_busbars"])
            f.addRow("Draw parallel busbars", self.draw_par)

            self.draw_ser = self._check(d["draw_series_jumpers"])
            f.addRow("Draw series jumpers", self.draw_ser)

            self.jumper_style = Qt.QComboBox()
            self.jumper_style.addItems(["paired", "rail", "single"])
            self.jumper_style.setCurrentText(str(d.get("series_jumper_style", "paired")))
            f.addRow("Series jumper style", self.jumper_style)

            self.busbar_solids = self._check(d["draw_busbar_solids"])
            f.addRow("Draw busbar solids", self.busbar_solids)

            self.busbar_width = self._dspin(d["busbar_width"], 0.1, 100.0)
            f.addRow("Busbar width (mm)", self.busbar_width)

            self.busbar_thickness = self._dspin(d["busbar_thickness"], 0.01, 20.0)
            f.addRow("Busbar thickness (mm)", self.busbar_thickness)

            self.draw_pol = self._check(d["draw_polarity_markers"])
            f.addRow("Draw polarity markers", self.draw_pol)

            self.draw_dots = self._check(d["draw_terminal_dots"])
            f.addRow("Draw terminal dots", self.draw_dots)

            self.dot_radius = self._dspin(d["terminal_dot_radius"], 0.1, 20.0)
            f.addRow("Terminal dot radius (mm)", self.dot_radius)

            self.pol_offset = self._dspin(d["polarity_offset"], 0.1, 50.0)
            f.addRow("Polarity offset (mm)", self.pol_offset)

            self.alt_layers = self._check(d["alternate_series_jumper_layers"])
            f.addRow("Alternate series jumper layers", self.alt_layers)

            self.top_z = self._dspin(d["top_layer_z"], -20.0, 20.0)
            f.addRow("Top layer Z offset", self.top_z)

            self.bot_z = self._dspin(d["bottom_layer_z"], -20.0, 20.0)
            f.addRow("Bottom layer Z offset", self.bot_z)

            return w

        def _make_score_tab(self) -> Qt.QWidget:
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            self.prefer_usage = self._check(d["prefer_shape_usage"])
            f.addRow("Prefer shape usage", self.prefer_usage)

            self.w_usage = self._dspin(d["shape_usage_weight"], 0.0, 50.0)
            f.addRow("Shape usage weight", self.w_usage)

            self.w_compact = self._dspin(d["compactness_weight"], 0.0, 50.0)
            f.addRow("Compactness weight", self.w_compact)

            self.w_center = self._dspin(d["center_bias_weight"], 0.0, 50.0)
            f.addRow("Center bias weight", self.w_center)

            self.w_rowshift = self._dspin(d["row_shift_weight"], 0.0, 50.0)
            f.addRow("Row shift weight", self.w_rowshift)

            self.w_boundary = self._dspin(d["boundary_margin_penalty_weight"], 0.0, 50.0)
            f.addRow("Boundary margin penalty weight", self.w_boundary)

            return w

        # ── Widget factories ──────────────────────────────────────────────

        @staticmethod
        def _dspin(val: float, lo: float, hi: float) -> Qt.QDoubleSpinBox:
            sb = Qt.QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setDecimals(3)
            sb.setValue(float(val))
            return sb

        @staticmethod
        def _spin(val: int, lo: int, hi: int) -> Qt.QSpinBox:
            sb = Qt.QSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(int(val))
            return sb

        @staticmethod
        def _check(val: bool) -> Qt.QCheckBox:
            cb = Qt.QCheckBox()
            cb.setChecked(bool(val))
            return cb

        # ── Result extraction ─────────────────────────────────────────────

        def values(self) -> dict:
            d = self._defs
            return {
                "mode":                          self.mode.currentText(),
                "cell_diameter":                 self.cell_diameter.value(),
                "clearance":                     self.clearance.value(),
                "cell_height":                   self.cell_height.value(),
                "target_s":                      self.target_s.value(),
                "target_p":                      self.target_p.value(),
                "make_2d":                       self.make_2d.isChecked(),
                "make_3d":                       self.make_3d.isChecked(),
                "make_labels":                   self.make_labels.isChecked(),
                "draw_all_candidates":           self.draw_all_candidates.isChecked(),
                "use_selected_edge_alignment":   self.use_edge_align.isChecked(),
                "fallback_angle_deg":            self.fallback_angle.value(),
                "edge_angle_offsets_deg":        self.edge_offsets.text(),
                "angles_deg":                    self.angles.text(),
                "colorize_series":               self.colorize_series.isChecked(),
                "snake_series_order":            self.snake.isChecked(),
                "draw_parallel_busbars":         self.draw_par.isChecked(),
                "draw_series_jumpers":           self.draw_ser.isChecked(),
                "series_jumper_style":           self.jumper_style.currentText(),
                "draw_busbar_solids":            self.busbar_solids.isChecked(),
                "busbar_width":                  self.busbar_width.value(),
                "busbar_thickness":              self.busbar_thickness.value(),
                "draw_alignment_arrow":          self.draw_arrow.isChecked(),
                "alignment_arrow_length":        self.arrow_length.value(),
                "draw_polarity_markers":         self.draw_pol.isChecked(),
                "polarity_offset":               self.pol_offset.value(),
                "draw_terminal_dots":            self.draw_dots.isChecked(),
                "terminal_dot_radius":           self.dot_radius.value(),
                "alternate_series_jumper_layers": self.alt_layers.isChecked(),
                "top_layer_z":                   self.top_z.value(),
                "bottom_layer_z":                self.bot_z.value(),
                "prefer_shape_usage":            self.prefer_usage.isChecked(),
                "shape_usage_weight":            self.w_usage.value(),
                "compactness_weight":            self.w_compact.value(),
                "center_bias_weight":            self.w_center.value(),
                "row_shift_weight":              self.w_rowshift.value(),
                "boundary_margin_penalty_weight": self.w_boundary.value(),
                # non-GUI fields forwarded unchanged
                "top_layer_color":               d["top_layer_color"],
                "bottom_layer_color":            d["bottom_layer_color"],
                "cell_fill_transparency":        d["cell_fill_transparency"],
            }

    dlg = SettingsDialog(defaults)
    if dlg.exec_():
        return dlg.values()
    return None
