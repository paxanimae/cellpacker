"""
cellpacker.ui.dialog
~~~~~~~~~~~~~~~~~~~~~
PySide2/6 settings dialog.  Returns a cfg dict on acceptance or ``None``
on cancellation.
"""

from __future__ import annotations

from cellpacker.defaults import DEFAULTS, CELL_PRESETS, save_defaults


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

            # All tabs are built — wire up cross-tab cascades.
            self.make_2d.toggled.connect(self._on_output_mode)
            self._on_output_mode()          # apply initial state
            self.cell_diameter.valueChanged.connect(self._refresh_busbar_list)
            self._refresh_busbar_list()     # initial catalog population

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

            save_btn = btns.addButton("Save as Defaults", Qt.QDialogButtonBox.ActionRole)
            save_btn.setToolTip(
                "Write current settings to cellpacker/defaults.json.\n"
                "These values will pre-populate the dialog on every future run."
            )
            save_btn.clicked.connect(self._save_as_defaults)

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

            self.auto_z_step = self._dspin(d.get("auto_z_step", 1.0), 0.1, 50.0, 1)
            self._row(az, "Layer step (mm)", self.auto_z_step,
                "Distance between the four physical layers along the sketch normal:\n\n"
                "  0 × step  Bottom face  — busbar strips, series jumpers, and\n"
                "                           polarity markers on the bottom side\n"
                "  1 × step  Cells        — cell circles / cylinders\n"
                "  2 × step  Top face     — busbar strips, series jumpers, and\n"
                "                           polarity markers on the top side\n"
                "  3 × step  Annotations  — S/P labels, PACK+/PACK−, arrow\n\n"
                "Which face a busbar or marker belongs to depends on the series\n"
                "group parity (odd groups have + at top, even groups have + at bottom).\n\n"
                "Increase step to spread layers further apart in the viewport.\n"
                "Uncheck Auto-Z to draw everything flat on the sketch plane.")

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
            # Solid strips and thickness only exist in 3D
            self.grp_solids.setEnabled(is_3d)

        # ── Tab: Routing ──────────────────────────────────────────────────

        def _make_routing_tab(self):
            d = self._defs
            try:
                from cellpacker.busbar_catalog import load_catalog
                self._catalog = load_catalog()
            except Exception:
                self._catalog = {"busbars": []}

            w   = Qt.QWidget()
            outer = Qt.QVBoxLayout(w)

            self.grp_busbars = Qt.QGroupBox("Busbars")
            self.grp_busbars.setCheckable(True)
            self.grp_busbars.setChecked(d.get("draw_busbars", True))
            self.grp_busbars.setToolTip(
                "Draw all busbar connections for the pack.\n"
                "Uncheck to skip busbar drawing entirely.")
            grp_lay = Qt.QVBoxLayout(self.grp_busbars)

            # ── Toolbar: add / remove + stock filter ─────────────────────
            toolbar = Qt.QWidget()
            tb_lay  = Qt.QHBoxLayout(toolbar)
            tb_lay.setContentsMargins(0, 0, 0, 0)
            tb_lay.setSpacing(4)

            self._btn_add_busbar = Qt.QPushButton("+")
            self._btn_add_busbar.setFixedWidth(28)
            self._btn_add_busbar.setToolTip("Add a custom busbar entry")

            self._btn_del_busbar = Qt.QPushButton("−")
            self._btn_del_busbar.setFixedWidth(28)
            self._btn_del_busbar.setEnabled(False)
            self._btn_del_busbar.setToolTip(
                "Delete selected busbar — only custom entries can be deleted")

            self.busbar_stock_filter = Qt.QCheckBox("In-stock only")
            self.busbar_stock_filter.setChecked(False)
            self.busbar_stock_filter.setToolTip(
                "Show only busbars marked in-stock.\n"
                "Toggle the checkbox next to any entry to mark it in-stock.")

            tb_lay.addWidget(self._btn_add_busbar)
            tb_lay.addWidget(self._btn_del_busbar)
            tb_lay.addStretch()
            tb_lay.addWidget(self.busbar_stock_filter)
            grp_lay.addWidget(toolbar)

            # ── List  +  SVG preview / details  (side by side) ───────────
            catalog_split = Qt.QSplitter(Qt.Qt.Horizontal)

            self.busbar_list = Qt.QListWidget()
            self.busbar_list.setMinimumHeight(110)
            self.busbar_list.setMaximumHeight(170)
            self.busbar_list.setToolTip(
                "Busbars compatible with the current cell diameter.\n"
                "  • Check the box to toggle in-stock status\n"
                "  • Select an entry to auto-fill Width / Thickness below")
            catalog_split.addWidget(self.busbar_list)

            right     = Qt.QWidget()
            right_lay = Qt.QVBoxLayout(right)
            right_lay.setContentsMargins(6, 0, 0, 0)
            right_lay.setSpacing(4)

            # SVG preview widget
            try:
                from PySide2.QtSvg import QSvgWidget
                self._busbar_svg = QSvgWidget()
                self._busbar_svg.setFixedSize(220, 64)
                self._busbar_svg.setToolTip("Top-down view of selected busbar")
                self._has_svg = True
            except ImportError:
                self._busbar_svg = Qt.QLabel("(QtSvg unavailable)")
                self._busbar_svg.setFixedSize(220, 64)
                self._busbar_svg.setAlignment(Qt.Qt.AlignCenter)
                self._has_svg = False

            right_lay.addWidget(self._busbar_svg)

            self.busbar_details = Qt.QLabel("")
            self.busbar_details.setWordWrap(True)
            self.busbar_details.setAlignment(
                Qt.Qt.AlignTop | Qt.Qt.AlignLeft)
            right_lay.addWidget(self.busbar_details)
            right_lay.addStretch()
            catalog_split.addWidget(right)
            catalog_split.setSizes([240, 230])
            grp_lay.addWidget(catalog_split)

            # ── Separator ────────────────────────────────────────────────
            sep = Qt.QFrame()
            sep.setFrameShape(Qt.QFrame.HLine)
            sep.setFrameShadow(Qt.QFrame.Sunken)
            grp_lay.addWidget(sep)

            # ── Strip settings ───────────────────────────────────────────
            fset = Qt.QFormLayout()
            fset.setContentsMargins(0, 4, 0, 0)

            self.busbar_width = self._dspin(d["busbar_width"], 0.1, 100.0)
            self._row(fset, "Width (mm)", self.busbar_width,
                "Physical width of the busbar strip in mm.\n"
                "Auto-filled when a catalog entry is selected.\n"
                "In wire mode this scales the line thickness in the viewport.")

            self.grp_solids = Qt.QGroupBox("Draw as solid strips")
            self.grp_solids.setCheckable(True)
            self.grp_solids.setChecked(d["draw_busbar_solids"])
            self.grp_solids.setToolTip(
                "Create solid 3D rectangular strips instead of wire lines.\n"
                "3D mode only — grayed out in 2D mode.")
            fsolid = Qt.QFormLayout(self.grp_solids)
            self.busbar_thickness = self._dspin(d["busbar_thickness"], 0.01, 20.0)
            self._row(fsolid, "Thickness (mm)", self.busbar_thickness,
                "Thickness of the solid busbar strip in mm.\n"
                "Auto-filled when a catalog entry is selected.\n"
                "Nickel strip: 0.10–0.30 mm.  Copper strip: 0.10–0.50 mm.")
            fset.addRow(self.grp_solids)

            grp_lay.addLayout(fset)
            outer.addWidget(self.grp_busbars)
            outer.addStretch()

            # Signals
            self.busbar_stock_filter.toggled.connect(self._refresh_busbar_list)
            self.busbar_list.itemSelectionChanged.connect(self._on_busbar_selected)
            self.busbar_list.itemChanged.connect(self._on_busbar_item_changed)
            self._btn_add_busbar.clicked.connect(self._add_busbar)
            self._btn_del_busbar.clicked.connect(self._remove_busbar)

            return w

        @staticmethod
        def _make_busbar_svg(entry: dict) -> bytes:
            """Return SVG bytes for a top-down view of *entry*."""
            W, H  = 220, 60
            p     = entry.get("p_rating", 1)
            frm   = entry.get("form", "strip")
            mat   = entry.get("material", "nickel")

            pad   = 8
            s_h   = H - 2 * pad
            pitch = (W - 2 * pad) / max(p, 1)
            s_w   = pitch * p
            sx    = (W - s_w) / 2
            sy    = float(pad)

            r_c = min(s_h * 0.36, pitch * 0.36)

            if mat == "copper":
                fill, stroke = "#d08040", "#905018"
            else:
                fill, stroke = "#b8b8b8", "#686868"

            svg = [
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{W}" height="{H}" '
                f'style="background:#2a2a2a;border-radius:4px">',
                f'<rect x="{sx:.1f}" y="{sy:.1f}" '
                f'width="{s_w:.1f}" height="{s_h:.1f}" '
                f'rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>',
            ]

            if frm == "perforated" and p > 1:
                slot_w = pitch * 0.38
                slot_h = s_h * 0.52
                for i in range(p - 1):
                    slot_x = sx + pitch * (i + 1) - slot_w / 2
                    slot_y = sy + (s_h - slot_h) / 2
                    svg.append(
                        f'<rect x="{slot_x:.1f}" y="{slot_y:.1f}" '
                        f'width="{slot_w:.1f}" height="{slot_h:.1f}" '
                        f'rx="1" fill="#2a2a2a" stroke="{stroke}" stroke-width="1"/>'
                    )

            for i in range(p):
                cx = sx + pitch * (i + 0.5)
                cy = sy + s_h / 2
                svg.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r_c:.1f}" '
                    f'fill="none" stroke="{stroke}" stroke-width="1.5" '
                    f'stroke-dasharray="3,2"/>'
                )

            svg.append("</svg>")
            return "\n".join(svg).encode("utf-8")

        def _refresh_busbar_list(self):
            """Repopulate the catalog list filtered by cell diameter and stock."""
            try:
                from cellpacker.busbar_catalog import compatible_busbars, in_stock_busbars
            except Exception:
                return

            diameter = self.cell_diameter.value()
            entries  = compatible_busbars(self._catalog, diameter)
            if self.busbar_stock_filter.isChecked():
                entries = in_stock_busbars(entries)

            prev_id = None
            sel = self.busbar_list.selectedItems()
            if sel:
                d = sel[0].data(Qt.Qt.UserRole)
                if d:
                    prev_id = d.get("id")

            self.busbar_list.blockSignals(True)
            self.busbar_list.clear()
            restore_row = None
            for i, entry in enumerate(entries):
                cf   = entry.get("cell_format") or "Universal"
                perf = " perf" if entry.get("form") == "perforated" else ""
                text = (f"{entry['p_rating']}P{perf}  "
                        f"{entry['width_mm']}×{entry['thickness_mm']} mm"
                        f"  [{cf}]")
                item = Qt.QListWidgetItem(text)
                item.setData(Qt.Qt.UserRole, entry)
                item.setFlags(item.flags() | Qt.Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Qt.Checked
                    if entry.get("in_stock", False)
                    else Qt.Qt.Unchecked
                )
                self.busbar_list.addItem(item)
                if entry.get("id") == prev_id:
                    restore_row = i
            self.busbar_list.blockSignals(False)

            if restore_row is not None:
                self.busbar_list.setCurrentRow(restore_row)
            elif self.busbar_list.count() > 0:
                self.busbar_list.setCurrentRow(0)

        def _on_busbar_selected(self):
            """Auto-fill width/thickness and refresh SVG preview + details pane."""
            sel   = self.busbar_list.selectedItems()
            entry = sel[0].data(Qt.Qt.UserRole) if sel else None

            self._btn_del_busbar.setEnabled(
                bool(entry) and entry.get("custom", False))

            if not entry:
                self.busbar_details.setText("")
                if self._has_svg:
                    _blank = b'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="64"/>'
                    self._busbar_svg.load(_blank)
                return

            self.busbar_width.setValue(entry["width_mm"])
            if self.make_3d.isChecked():
                self.busbar_thickness.setValue(entry["thickness_mm"])

            if self._has_svg:
                self._busbar_svg.load(self._make_busbar_svg(entry))

            cf_str     = entry.get("cell_format") or "Universal"
            lo, hi     = entry.get("compatible_diameter_range", [0, 999])
            hi_str     = "∞" if hi >= 999 else f"{hi:.1f} mm"
            stock_str  = "✓" if entry.get("in_stock") else "✗"
            custom_str = "Yes" if entry.get("custom") else "No (factory)"
            self.busbar_details.setText(
                f"<small>"
                f"<b>Material:</b> {entry.get('material','—').capitalize()}<br>"
                f"<b>Form:</b> {entry.get('form','—')}<br>"
                f"<b>Size:</b> {entry['width_mm']} × {entry['thickness_mm']} mm<br>"
                f"<b>Cell format:</b> {cf_str}<br>"
                f"<b>Compat.:</b> {lo:.1f} – {hi_str}<br>"
                f"<b>In stock:</b> {stock_str}  "
                f"<b>Custom:</b> {custom_str}"
                f"</small>"
            )

        def _on_busbar_item_changed(self, item):
            """Persist the in_stock checkbox state to busbars.json."""
            entry = item.data(Qt.Qt.UserRole)
            if entry is None:
                return
            in_stock = item.checkState() == Qt.Qt.Checked
            for b in self._catalog.get("busbars", []):
                if b.get("id") == entry.get("id"):
                    b["in_stock"] = in_stock
                    break
            try:
                from cellpacker.busbar_catalog import save_catalog
                save_catalog(self._catalog)
            except Exception as exc:
                print(f"CellPacker: could not save busbar catalog — {exc}")

        def _add_busbar(self):
            """Open a dialog to create a new custom busbar entry."""
            dlg = Qt.QDialog(self)
            dlg.setWindowTitle("Add Custom Busbar")
            f   = Qt.QFormLayout(dlg)
            f.setFieldGrowthPolicy(Qt.QFormLayout.ExpandingFieldsGrow)

            name_edit  = Qt.QLineEdit()
            mat_combo  = Qt.QComboBox()
            mat_combo.addItems(
                ["nickel", "copper", "nickel-plated-copper", "aluminium"])
            form_combo = Qt.QComboBox()
            form_combo.addItems(["strip", "perforated", "solid-sheet"])
            p_spin = Qt.QSpinBox()
            p_spin.setRange(1, 20)
            w_spin  = self._dspin(8.0,   0.1,  200.0)
            t_spin  = self._dspin(0.15,  0.01,  20.0)
            lo_spin = self._dspin(10.0,  0.0,  999.0)
            hi_spin = self._dspin(999.0, 0.0, 9999.0)
            off_chk = self._check(False)

            f.addRow("Name", name_edit)
            f.addRow("Material", mat_combo)
            f.addRow("Form", form_combo)
            f.addRow("P-rating", p_spin)
            f.addRow("Width (mm)", w_spin)
            f.addRow("Thickness (mm)", t_spin)
            f.addRow("Min cell diameter (mm)", lo_spin)
            f.addRow("Max cell diameter (mm)", hi_spin)
            f.addRow("Offset capable", off_chk)

            btns = Qt.QDialogButtonBox(
                Qt.QDialogButtonBox.Ok | Qt.QDialogButtonBox.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            f.addRow(btns)

            if dlg.exec_() != Qt.QDialog.Accepted:
                return
            name = name_edit.text().strip()
            if not name:
                return

            import re as _re, time as _time
            safe = _re.sub(r"[^a-z0-9]+", "_",
                           name.lower()).strip("_") or "busbar"
            uid  = f"custom_{safe}_{int(_time.time()) % 100000}"

            entry = {
                "id": uid, "name": name,
                "cell_format": None,
                "compatible_diameter_range": [lo_spin.value(), hi_spin.value()],
                "material": mat_combo.currentText(),
                "form": form_combo.currentText(),
                "p_rating": p_spin.value(),
                "width_mm": w_spin.value(),
                "thickness_mm": t_spin.value(),
                "offset": off_chk.isChecked(),
                "in_stock": True,
                "custom": True,
                "preview": None,
            }
            self._catalog.setdefault("busbars", []).append(entry)
            try:
                from cellpacker.busbar_catalog import save_catalog
                save_catalog(self._catalog)
            except Exception as exc:
                print(f"CellPacker: could not save busbar catalog — {exc}")
            self._refresh_busbar_list()

        def _remove_busbar(self):
            """Remove the selected custom busbar entry from the catalog."""
            sel   = self.busbar_list.selectedItems()
            entry = sel[0].data(Qt.Qt.UserRole) if sel else None
            if not entry or not entry.get("custom"):
                return
            self._catalog["busbars"] = [
                b for b in self._catalog.get("busbars", [])
                if b.get("id") != entry.get("id")
            ]
            try:
                from cellpacker.busbar_catalog import save_catalog
                save_catalog(self._catalog)
            except Exception as exc:
                print(f"CellPacker: could not save busbar catalog — {exc}")
            self._refresh_busbar_list()

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
                "auto_z_step":   self.auto_z_step.value(),
                # Routing
                "draw_busbars":          self.grp_busbars.isChecked(),
                "draw_busbar_solids":    is_3d and self.grp_solids.isChecked(),
                "busbar_width":          self.busbar_width.value(),
                "busbar_thickness":      self.busbar_thickness.value() if is_3d else 0.0,
                "busbar_catalog_id":     (
                    self.busbar_list.selectedItems()[0].data(
                        Qt.Qt.UserRole)["id"]
                    if self.busbar_list.selectedItems() else None
                ),
                "busbar_p_rating":       (
                    self.busbar_list.selectedItems()[0].data(
                        Qt.Qt.UserRole).get("p_rating", 1)
                    if self.busbar_list.selectedItems() else 1
                ),
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
                "busbar_color_top":              d["busbar_color_top"],
                "busbar_color_bottom":           d["busbar_color_bottom"],
                "cell_fill_transparency":        d["cell_fill_transparency"],
            }

        def _save_as_defaults(self):
            save_defaults(self.values())
            Qt.QMessageBox.information(
                self, "Saved",
                "Current settings saved as defaults.\n"
                "They will pre-populate this dialog on future runs."
            )

        def reject(self):
            if cleanup_fn is not None:
                cleanup_fn()
            super().reject()

    dlg = SettingsDialog(defaults)
    if dlg.exec_():
        return dlg.values()
    return None
