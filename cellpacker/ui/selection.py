"""
cellpacker.ui.selection
~~~~~~~~~~~~~~~~~~~~~~~~
FreeCAD selection helpers: extract the target sketch and an optional
alignment edge from the current GUI selection.
"""

from __future__ import annotations


def get_selected_sketch_and_edge() -> tuple:
    """
    Return ``(sketch_obj, edge_or_None)`` from the current FreeCAD selection.

    The user must select at least one object that has a closed wire (the
    pack-outline sketch).  If they also Ctrl-select a straight edge, that
    edge is returned for grid-alignment purposes.

    Raises
    ------
    RuntimeError
        If no valid sketch-like object is selected.
    """
    import Part
    import FreeCADGui as Gui

    sel_ex = Gui.Selection.getSelectionEx()
    if not sel_ex:
        raise RuntimeError(
            "Nothing selected. Select a closed sketch, and optionally "
            "one straight edge for alignment."
        )

    sketch_obj = None
    for s in sel_ex:
        if hasattr(s.Object, "Shape") and s.Object.Shape.Wires:
            sketch_obj = s.Object
            break

    if sketch_obj is None:
        raise RuntimeError("Could not find a selected object with closed wires.")

    selected_edge = None
    for s in sel_ex:
        for sub in s.SubObjects:
            if isinstance(sub, Part.Edge) and len(sub.Vertexes) == 2:
                selected_edge = sub
                break
        if selected_edge is not None:
            break

    return sketch_obj, selected_edge
