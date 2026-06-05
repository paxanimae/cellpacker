"""
cellpacker.geometry.face
~~~~~~~~~~~~~~~~~~~~~~~~
Helpers for extracting a local-coordinate ``Part.Face`` from a FreeCAD
sketch object and testing whether circles fit inside it.
"""

import math


def get_local_face(sketch_obj):
    """
    Return a ``Part.Face`` built from the first closed wire of *sketch_obj*,
    expressed in the sketch's **local** coordinate system.

    Raises
    ------
    ValueError
        If no closed wire is found.
    """
    import Part

    shape_global = sketch_obj.Shape
    if not shape_global.Wires:
        raise ValueError("Selected object has no wires. Select a closed sketch.")

    shape_local = shape_global.copy()
    shape_local.Placement = (
        sketch_obj.Placement.inverse().multiply(shape_local.Placement)
    )

    for wire in shape_local.Wires:
        if wire.isClosed():
            return Part.Face(wire)

    raise ValueError("No closed wire found in the selected sketch.")


def point_inside_face(face, x: float, y: float, tol: float = 0.05) -> bool:
    """Return ``True`` if the 2-D point *(x, y)* lies inside *face*."""
    import FreeCAD as App

    return face.isInside(App.Vector(x, y, 0), tol, True)


def circle_fits(face, cx: float, cy: float, radius: float, samples: int = 24) -> bool:
    """
    Return ``True`` if a circle of *radius* centred at *(cx, cy)* fits
    entirely inside *face*.

    The centre is checked first; then *samples* evenly-spaced perimeter
    points are tested.  Using 24 samples (vs. the original 16) catches
    tighter concave corners more reliably.
    """
    if not point_inside_face(face, cx, cy):
        return False

    for i in range(samples):
        t = 2 * math.pi * i / samples
        if not point_inside_face(face, cx + radius * math.cos(t), cy + radius * math.sin(t)):
            return False

    return True


def point_to_boundary_distance(face, x: float, y: float) -> float:
    """
    Return the distance from *(x, y)* to the nearest point on the boundary
    of *face*.  Returns 0.0 on failure.
    """
    import Part

    try:
        v = Part.Vertex(Part.Point(x, y, 0).toShape())  # robust construction
        return float(face.distToShape(v)[0])
    except Exception:
        try:
            import FreeCAD as App
            v = Part.Vertex(App.Vector(x, y, 0))
            return float(face.distToShape(v)[0])
        except Exception:
            return 0.0
