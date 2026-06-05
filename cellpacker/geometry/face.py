"""
cellpacker.geometry.face
~~~~~~~~~~~~~~~~~~~~~~~~
Extracts a local-coordinate Part.Face from a FreeCAD sketch and tests
whether circles fit inside it.

Key invariant
-------------
Everything returned by this module is in **local sketch coordinates** —
i.e. the flat 2-D plane of the sketch, with Z=0.  The hex grid is
generated in that same space, and only converted to world coords at draw
time via ``to_global()``.

For Sketcher::SketchObject the shape vertices are already in local 2-D
coords (FreeCAD keeps them that way internally).  We verify this by
checking that all Z values are near zero; if not, we apply the inverse
placement.
"""

import math


def get_local_face(sketch_obj):
    """
    Return a ``Part.Face`` in local (2-D) sketch coordinates.

    Raises
    ------
    ValueError  – no closed wire found.
    """
    import Part
    import FreeCAD as App

    shape = sketch_obj.Shape
    if not shape.Wires:
        raise ValueError(
            f"'{sketch_obj.Label}' has no wires. Select a closed sketch."
        )

    # Check whether the shape is already flat (all Z ≈ 0).
    # If it is, use it as-is.  If not, apply inverse placement.
    all_z = [v.Z for v in shape.Vertexes]
    already_local = all_z and max(abs(z) for z in all_z) < 1.0

    if already_local:
        shape_local = shape.copy()
        print(f"BatteryPackLayoutTool: sketch shape is already local (max |Z| = "
              f"{max(abs(z) for z in all_z):.4f})")
    else:
        shape_local = shape.copy()
        inv = sketch_obj.Placement.inverse()
        shape_local = shape_local.transformGeometry(inv.toMatrix())
        all_z2 = [v.Z for v in shape_local.Vertexes]
        print(f"BatteryPackLayoutTool: applied inverse placement, "
              f"max |Z| after = {max(abs(z) for z in all_z2):.4f}")

    for wire in shape_local.Wires:
        if wire.isClosed():
            try:
                face = Part.Face(wire)
                bb = face.BoundBox
                print(f"BatteryPackLayoutTool: face bbox "
                      f"X=[{bb.XMin:.1f}, {bb.XMax:.1f}] "
                      f"Y=[{bb.YMin:.1f}, {bb.YMax:.1f}]")
                return face
            except Exception as e:
                print(f"BatteryPackLayoutTool: Part.Face failed ({e}), trying next wire")

    raise ValueError(
        f"No usable closed wire found in '{sketch_obj.Label}'. "
        "Make sure the sketch boundary is fully closed."
    )


def point_inside_face(face, x: float, y: float, tol: float = 0.05) -> bool:
    import FreeCAD as App
    return face.isInside(App.Vector(x, y, 0), tol, True)


def circle_fits(face, cx: float, cy: float, radius: float, samples: int = 24) -> bool:
    if not point_inside_face(face, cx, cy):
        return False
    for i in range(samples):
        t = 2 * math.pi * i / samples
        if not point_inside_face(face, cx + radius * math.cos(t), cy + radius * math.sin(t)):
            return False
    return True


def point_to_boundary_distance(face, x: float, y: float) -> float:
    import Part
    import FreeCAD as App
    try:
        v = Part.Vertex(App.Vector(x, y, 0))
        return float(face.distToShape(v)[0])
    except Exception:
        return 0.0
