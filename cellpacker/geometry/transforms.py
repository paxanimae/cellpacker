"""
cellpacker.geometry.transforms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure-Python 2-D rotation helpers and FreeCAD coordinate
conversion utilities.  No FreeCAD imports required for the
pure math functions, making them unit-testable outside FreeCAD.
"""

import math


# ── Pure-math helpers ──────────────────────────────────────────────────────

def rotate_2d(x: float, y: float, angle_deg: float) -> tuple[float, float]:
    """Rotate point (x, y) by *angle_deg* degrees counter-clockwise."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    return (x * ca - y * sa, x * sa + y * ca)


def inverse_rotate_2d(x: float, y: float, angle_deg: float) -> tuple[float, float]:
    """Inverse of :func:`rotate_2d`."""
    return rotate_2d(x, y, -angle_deg)


# ── FreeCAD-dependent helpers ─────────────────────────────────────────────

def to_global(sketch_obj, x: float, y: float, z: float = 0.0):
    """Transform a local-sketch (x, y, z) point to world coordinates."""
    import FreeCAD as App  # deferred so module is importable without FreeCAD
    return sketch_obj.Placement.multVec(App.Vector(x, y, z))


def get_edge_local_endpoints(
    sketch_obj, edge
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return the two endpoints of *edge* in local sketch coordinates."""
    inv = sketch_obj.Placement.inverse()
    p1 = inv.multVec(edge.Vertexes[0].Point)
    p2 = inv.multVec(edge.Vertexes[1].Point)
    return (p1.x, p1.y), (p2.x, p2.y)


def get_edge_angle_in_local_coords(
    sketch_obj, edge, fallback_angle_deg: float = 0.0
) -> float:
    """
    Return the angle (degrees) of *edge* expressed in the local coordinate
    system of *sketch_obj*.  Falls back to *fallback_angle_deg* when *edge*
    is ``None`` or degenerate.
    """
    if edge is None:
        return fallback_angle_deg

    p1_global = edge.Vertexes[0].Point
    p2_global = edge.Vertexes[1].Point
    inv = sketch_obj.Placement.inverse()
    p1 = inv.multVec(p1_global)
    p2 = inv.multVec(p2_global)

    dx = p2.x - p1.x
    dy = p2.y - p1.y
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        raise ValueError("Selected edge has zero length in local coordinates.")

    return math.degrees(math.atan2(dy, dx))
