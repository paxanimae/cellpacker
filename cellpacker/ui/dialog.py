"""
cellpacker.ui.dialog
~~~~~~~~~~~~~~~~~~~~~
PySide2 settings dialog.  Returns a cfg dict on acceptance or ``None``
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
            self.resize(800, 680)
            self._defs = defs

            root = Qt.QVBoxLayout(self)
            tabs = Qt.QTabWidget()
            root.addWidget(tabs)

            tabs.addTab(self._make_help_tab(),      "Help")
            tabs.addTab(self._make_pack_tab(),      "Pack")
            tabs.addTab(self._make_display_tab(),   "Display")
            tabs.addTab(self._make_routing_tab(),   "Routing")
            tabs.addTab(self._make_align_tab(),     "Alignment")
            tabs.addTab(self._make_score_tab(),     "Scoring")

            # Apply initial Auto-Z state (connects/disconnects cell_height signal).
            self._on_auto_z(self.auto_z.isChecked())

            btns = Qt.QDialogButtonBox(
                Qt.QDialogButtonBox.Ok | Qt.QDialogButtonBox.Cancel
            )
            btns.accepted.connect(self.accept)
            btns.rejected.connect(self.reject)

            if preview_fn is not None:
                prev = btns.addButton("Preview", Qt.QDialogButtonBox.ActionRole)
                prev.setToolTip(
                    "Run the layout with current settings and draw into the viewport.\n"
                    "Adjust settings and click again to update."
                )
                prev.clicked.connect(lambda: preview_fn(self.values()))

            root.addWidget(btns)

        # ── Helpers ───────────────────────────────────────────────────────

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
        def _sep(text=""):
            lbl = Qt.QLabel(f"<b>{text}</b>" if text else "")
            return lbl

        # ── Tab: Help ─────────────────────────────────────────────────────

        def _make_help_tab(self):
            w = Qt.QWidget()
            lay = Qt.QVBoxLayout(w)
            te = Qt.QTextEdit()
            te.setReadOnly(True)
            te.setHtml("""
<h2>Battery Pack Layout Tool</h2>
<p><b>1.</b> Draw a closed sketch for the pack outline. Select it (Ctrl-select
a straight edge to align the grid to it), then run this macro.</p>
<p><b>2.</b> Set cell type, series groups (S) and parallel cells (P)
in the <b>Pack</b> tab.</p>
<p><b>3.</b> Choose what to render in the <b>Display</b> tab.
Enable <i>Auto-Z</i> to separate layers by their physical height —
minus terminal at the base, cells in the middle, plus terminal at the top.</p>
<p><b>4.</b> Configure busbars in the <b>Routing</b> tab.
Uncheck the group header to disable that busbar type entirely.</p>
<p><b>5.</b> Click <b>Preview</b> to draw into the viewport without closing
the dialog. Adjust and preview as many times as you like, then click
<b>OK</b> to finalise.</p>
<pre>
  Candidates:          Selected 5s5p:       Busbars:
   o o o o o           S01: + + + + +       ─── parallel rail (+ terminal face)
    o o o o             S02: - - - - -       ─── parallel rail (− terminal face)
   o o o o o           S03: + + + + +       ╱   series jumpers (between groups)
</pre>
""")
            lay.addWidget(te)
            return w

        # ── Tab: Pack ─────────────────────────────────────────────────────

        def _make_pack_tab(self):
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            # Cell type preset
            self.cell_type = Qt.QComboBox()
            self.cell_type.addItem("Custom")
            for name in CELL_PRESETS:
                self.cell_type.addItem(name)
            f.addRow("Cell type", self.cell_type)

            self.cell_diameter = self._dspin(d["cell_diameter"], 1.0, 100.0)
            f.addRow("Cell diameter (mm)", self.cell_diameter)

            self.clearance = self._dspin(d["clearance"], 0.0, 20.0)
            f.addRow("Clearance (mm)", self.clearance)

            self.cell_height = self._dspin(d["cell_height"], 1.0, 200.0)
            f.addRow("Cell height (mm)", self.cell_height)

            f.addRow(self._sep())
            f.addRow(self._sep("Pack topology"))

            self.target_s = self._spin(d["target_s"], 1, 200)
            f.addRow("Series groups (S)", self.target_s)

            self.target_p = self._spin(d["target_p"], 1, 100)
            f.addRow("Parallel cells (P)", self.target_p)

            f.addRow(self._sep())
            f.addRow(self._sep("Series layout"))

            self.colorize_series = self._check(d["colorize_series"])
            f.addRow("Colorize by series group", self.colorize_series)

            self.snake = self._check(d["snake_series_order"])
            f.addRow("Snake series order", self.snake)

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

            # ── Render objects ────────────────────────────────────────────
            f.addRow(self._sep("Render objects"))
            self.make_2d = self._check(d["make_2d"])
            f.addRow("Draw 2D cell disks", self.make_2d)
            self.make_3d = self._check(d["make_3d"])
            f.addRow("Draw 3D cell cylinders", self.make_3d)
            self.make_labels = self._check(d["make_labels"])
            f.addRow("Draw S/P labels on cells", self.make_labels)

            # ── Candidate overlay ─────────────────────────────────────────
            f.addRow(self._sep())
            f.addRow(self._sep("Candidate cell overlay"))
            self.show_candidates = self._check(d.get("show_candidates", True))
            f.addRow("Show all candidate positions", self.show_candidates)
            self.candidates_visible = self._check(d.get("candidates_visible", True))
            f.addRow("  Visible in viewport", self.candidates_visible)
            self.show_candidates.stateChanged.connect(
                lambda s: self.candidates_visible.setEnabled(bool(s))
            )
            self.candidates_visible.setEnabled(self.show_candidates.isChecked())

            # ── Annotations ───────────────────────────────────────────────
            f.addRow(self._sep())
            f.addRow(self._sep("Annotations"))
            self.draw_pol = self._check(d["draw_polarity_markers"])
            f.addRow("Draw (+) / (-) markers per cell", self.draw_pol)
            self.draw_dots = self._check(d["draw_terminal_dots"])
            f.addRow("Draw terminal dots", self.draw_dots)
            self.dot_radius = self._dspin(d["terminal_dot_radius"], 0.1, 20.0)
            f.addRow("  Dot radius (mm)", self.dot_radius)
            self.pol_offset = self._dspin(d["polarity_offset"], 0.1, 50.0)
            f.addRow("  Polarity offset from centre (mm)", self.pol_offset)
            self.draw_pack_labels = self._check(d.get("draw_pack_terminal_labels", True))
            f.addRow("Draw PACK+ / PACK- output labels", self.draw_pack_labels)
            self.draw_arrow = self._check(d["draw_alignment_arrow"])
            f.addRow("Draw grid alignment arrow", self.draw_arrow)
            self.arrow_length = self._dspin(d["alignment_arrow_length"], 1.0, 1000.0)
            f.addRow("  Arrow length (mm)", self.arrow_length)

            # ── Z-layering ────────────────────────────────────────────────
            f.addRow(self._sep())
            f.addRow(self._sep("Z-layering"))
            self.auto_z = self._check(d.get("auto_z", True))
            f.addRow("Auto-Z (physical layer heights)", self.auto_z)
            note = Qt.QLabel(
                "  Auto-Z ON: layers follow physical cell height.\n"
                "  Auto-Z OFF: everything drawn flat on the sketch plane (Z = 0)."
            )
            note.setWordWrap(True)
            f.addRow(note)
            self.minus_busbar_z = self._dspin(d["minus_busbar_z"], -500.0, 500.0)
            f.addRow("  − terminal layer Z (mm)", self.minus_busbar_z)
            self.plus_busbar_z = self._dspin(d["plus_busbar_z"], -500.0, 500.0)
            f.addRow("  + terminal layer Z (mm)", self.plus_busbar_z)

            self._auto_z_signal_connected = False
            self.auto_z.stateChanged.connect(self._on_auto_z)

            scroll.setWidget(inner)
            outer = Qt.QVBoxLayout(w)
            outer.addWidget(scroll)
            return w

        def _on_auto_z(self, state):
            on = bool(state)
            self.plus_busbar_z.setEnabled(not on)
            self.minus_busbar_z.setEnabled(not on)
            if on and not self._auto_z_signal_connected:
                self.cell_height.valueChanged.connect(self.plus_busbar_z.setValue)
                self._auto_z_signal_connected = True
                self.plus_busbar_z.setValue(self.cell_height.value())
                self.minus_busbar_z.setValue(0.0)
            elif not on and self._auto_z_signal_connected:
                self.cell_height.valueChanged.disconnect(self.plus_busbar_z.setValue)
                self._auto_z_signal_connected = False
                self.plus_busbar_z.setValue(0.0)
                self.minus_busbar_z.setValue(0.0)

        # ── Tab: Routing ──────────────────────────────────────────────────

        def _make_routing_tab(self):
            d = self._defs
            w = Qt.QWidget()
            lay = Qt.QVBoxLayout(w)

            # ── Parallel busbars ──────────────────────────────────────────
            self.grp_par = Qt.QGroupBox("Parallel busbars")
            self.grp_par.setCheckable(True)
            self.grp_par.setChecked(d["draw_parallel_busbars"])
            fpar = Qt.QFormLayout(self.grp_par)

            self.busbar_solids = self._check(d["draw_busbar_solids"])
            fpar.addRow("Draw as solid strips", self.busbar_solids)
            self.busbar_width = self._dspin(d["busbar_width"], 0.1, 100.0)
            fpar.addRow("Width (mm)", self.busbar_width)
            self.busbar_thickness = self._dspin(d["busbar_thickness"], 0.01, 20.0)
            fpar.addRow("Thickness (mm)", self.busbar_thickness)
            lay.addWidget(self.grp_par)

            # ── Series jumpers ────────────────────────────────────────────
            self.grp_ser = Qt.QGroupBox("Series jumpers")
            self.grp_ser.setCheckable(True)
            self.grp_ser.setChecked(d["draw_series_jumpers"])
            fser = Qt.QFormLayout(self.grp_ser)

            self.jumper_style = Qt.QComboBox()
            self.jumper_style.addItems(["paired", "rail", "single"])
            self.jumper_style.setCurrentText(str(d.get("series_jumper_style", "paired")))
            fser.addRow("Jumper style", self.jumper_style)
            lay.addWidget(self.grp_ser)

            lay.addStretch()
            return w

        # ── Tab: Alignment ────────────────────────────────────────────────

        def _make_align_tab(self):
            w = Qt.QWidget()
            f = Qt.QFormLayout(w)
            d = self._defs

            self.use_edge_align = self._check(d["use_selected_edge_alignment"])
            f.addRow("Align grid to selected edge", self.use_edge_align)

            self.fallback_angle = self._dspin(d["fallback_angle_deg"], -360.0, 360.0)
            f.addRow("Fallback angle (deg)", self.fallback_angle)

            self.edge_offsets = Qt.QLineEdit(str(d["edge_angle_offsets_deg"]))
            f.addRow("Edge angle offsets (deg, CSV)", self.edge_offsets)

            self.angles = Qt.QLineEdit(str(d["angles_deg"]))
            f.addRow("Angle sweep (deg, CSV)", self.angles)

            return w

        # ── Tab: Scoring ──────────────────────────────────────────────────

        def _make_score_tab(self):
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

        # ── Result extraction ─────────────────────────────────────────────

        def values(self) -> dict:
            d = self._defs
            return {
                # Cell geometry
                "cell_diameter":                 self.cell_diameter.value(),
                "clearance":                     self.clearance.value(),
                "cell_height":                   self.cell_height.value(),
                # Pack topology
                "target_s":                      self.target_s.value(),
                "target_p":                      self.target_p.value(),
                "colorize_series":               self.colorize_series.isChecked(),
                "snake_series_order":            self.snake.isChecked(),
                # Output flags
                "make_2d":                       self.make_2d.isChecked(),
                "make_3d":                       self.make_3d.isChecked(),
                "make_labels":                   self.make_labels.isChecked(),
                "show_candidates":               self.show_candidates.isChecked(),
                "candidates_visible":            self.candidates_visible.isChecked(),
                # Annotations
                "draw_polarity_markers":         self.draw_pol.isChecked(),
                "polarity_offset":               self.pol_offset.value(),
                "draw_terminal_dots":            self.draw_dots.isChecked(),
                "terminal_dot_radius":           self.dot_radius.value(),
                "draw_pack_terminal_labels":     self.draw_pack_labels.isChecked(),
                "draw_alignment_arrow":          self.draw_arrow.isChecked(),
                "alignment_arrow_length":        self.arrow_length.value(),
                # Z-layering
                "auto_z":                        self.auto_z.isChecked(),
                "plus_busbar_z":                 self.plus_busbar_z.value(),
                "minus_busbar_z":                self.minus_busbar_z.value(),
                # Routing
                "draw_parallel_busbars":         self.grp_par.isChecked(),
                "draw_busbar_solids":            self.busbar_solids.isChecked(),
                "busbar_width":                  self.busbar_width.value(),
                "busbar_thickness":              self.busbar_thickness.value(),
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
                # Non-GUI fields forwarded unchanged
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
