"""
cellpacker.ui.selection
~~~~~~~~~~~~~~~~~~~~~~~~
FreeCAD selection helpers: extract the target sketch and an optional
alignment edge from the current GUI selection.

Handles the common case where the sketch lives inside a Part Design Body.
Priority order for sketch detection:
  1. Sketcher::SketchObject  (most reliable)
  2. Any object whose Shape has exactly closed wire(s) and no solid faces
     (avoids picking up the Body itself)
  3. Fallback: first object with any wires
"""

from __future__ import annotations


def get_selected_sketch_and_edge() -> tuple:
    """
    Return ``(sketch_obj, edge_or_None)`` from the current FreeCAD selection.

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

    # Pass 1: prefer an actual Sketcher::SketchObject
    for s in sel_ex:
        obj = s.Object
        if obj.TypeId == "Sketcher::SketchObject":
            sketch_obj = obj
            break

    # Pass 2: any object with closed wires but no solid (avoids Body)
    if sketch_obj is None:
        for s in sel_ex:
            obj = s.Object
            if not hasattr(obj, "Shape"):
                continue
            shape = obj.Shape
            if not shape.Wires:
                continue
            # Reject if the shape has solid faces (it's a 3D body, not a sketch)
            if shape.Solids:
                continue
            if any(w.isClosed() for w in shape.Wires):
                sketch_obj = obj
                break

    # Pass 3: last resort — any object with wires at all
    if sketch_obj is None:
        for s in sel_ex:
            obj = s.Object
            if hasattr(obj, "Shape") and obj.Shape.Wires:
                sketch_obj = obj
                break

    if sketch_obj is None:
        raise RuntimeError(
            "Could not find a valid sketch in the selection.\n"
            "Make sure you select the Sketch object directly (not the Body)."
        )

    print(f"BatteryPackLayoutTool: using sketch '{sketch_obj.Label}' "
          f"(TypeId: {sketch_obj.TypeId})")

    # Alignment edge
    selected_edge = None
    for s in sel_ex:
        for sub in s.SubObjects:
            if isinstance(sub, Part.Edge) and len(sub.Vertexes) == 2:
                selected_edge = sub
                break
        if selected_edge is not None:
            break

    return sketch_obj, selected_edge
