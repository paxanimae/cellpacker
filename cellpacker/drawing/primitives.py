"""
cellpacker.drawing.primitives
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Thin wrappers around FreeCAD Part / Draft objects.

Each function creates exactly one document object, adds it to *group*,
optionally styles it, and returns it.  Nothing here does layout logic.
"""

from __future__ import annotations
import FreeCAD as App
import Part
import Draft


# ── View styling ──────────────────────────────────────────────────────────

def _apply_color(obj, rgb: tuple | None) -> None:
    """Apply *rgb* to all recognised color attributes on *obj*'s ViewObject."""
    if rgb is None or not hasattr(obj, "ViewObject"):
        return
    for attr in ("LineColor", "ShapeColor", "TextColor"):
        try:
            setattr(obj.ViewObject, attr, rgb)
        except Exception:
            pass


def _apply_busbar_style(obj, rgb: tuple | None) -> None:
    _apply_color(obj, rgb)
    if hasattr(obj, "ViewObject"):
        try:
            obj.ViewObject.LineWidth = 4.0
        except Exception:
            pass


# ── Primitives ────────────────────────────────────────────────────────────

def draw_circle(
    doc,
    global_pt: App.Vector,
    radius: float,
    label: str,
    group,
    color: tuple | None = None,
) -> object:
    """
    Draw a filled 2-D cell disk as a ``Part.Face`` (Draft circles are
    wire-only and don't honour ``ShapeColor``).
    """
    edge = Part.makeCircle(radius, global_pt, App.Vector(0, 0, 1))
    face = Part.Face(Part.Wire([edge]))
    obj = doc.addObject("Part::Feature", label)
    obj.Shape = face
    group.addObject(obj)
    _apply_color(obj, color)
    try:
        obj.ViewObject.DisplayMode = "Flat Lines"
    except Exception:
        pass
    return obj


def draw_cylinder(
    doc,
    global_pt: App.Vector,
    radius: float,
    height: float,
    rotation: App.Rotation,
    label: str,
    group,
    color: tuple | None = None,
) -> object:
    """Draw a 3-D cylinder representing a physical cell."""
    cyl = doc.addObject("Part::Cylinder", label)
    cyl.Radius = radius
    cyl.Height = height
    cyl.Placement = App.Placement(global_pt, rotation)
    group.addObject(cyl)
    _apply_color(cyl, color)
    return cyl


def draw_text(
    doc,
    global_pt: App.Vector,
    text: str,
    label: str,
    group,
    color: tuple | None = None,
) -> object:
    """Place a Draft text label at *global_pt*."""
    txt = Draft.makeText([text], point=global_pt)
    txt.Label = label
    group.addObject(txt)
    _apply_color(txt, color)
    return txt


def draw_polyline(
    doc,
    global_points: list[App.Vector],
    label: str,
    group,
    color: tuple | None = None,
    closed: bool = False,
) -> object:
    """Draw a Draft wire through *global_points*."""
    wire = Draft.makeWire(global_points, closed=closed, face=False)
    wire.Label = label
    group.addObject(wire)
    _apply_busbar_style(wire, color)
    return wire


def draw_circle_outline(
    doc,
    global_pt: App.Vector,
    radius: float,
    label: str,
    group,
    color: tuple | None = None,
) -> object:
    """Draw a Draft circle (wire outline, for terminal dots)."""
    circ = Draft.makeCircle(
        radius, placement=App.Placement(global_pt, App.Rotation())
    )
    circ.Label = label
    group.addObject(circ)
    _apply_color(circ, color)
    return circ


def draw_busbar_strip(
    doc,
    p1: App.Vector,
    p2: App.Vector,
    width: float,
    thickness: float,
    label: str,
    group,
    color: tuple | None = None,
) -> object | None:
    """Extrude a rectangular busbar strip between *p1* and *p2*."""
    v = p2.sub(p1)
    length = v.Length
    if length < 0.001:
        return None

    ux = App.Vector(v.x / length, v.y / length, v.z / length)
    up = App.Vector(0, 0, 1)
    side = up.cross(ux)
    if side.Length < 0.001:
        side = App.Vector(1, 0, 0)
    side.normalize()

    half_w = width / 2.0
    a = p1.add(App.Vector(side).multiply(half_w))
    b = p1.sub(App.Vector(side).multiply(half_w))
    c = p2.sub(App.Vector(side).multiply(half_w))
    d = p2.add(App.Vector(side).multiply(half_w))

    poly = Part.makePolygon([a, b, c, d, a])
    face = Part.Face(poly)
    solid = face.extrude(App.Vector(0, 0, thickness))

    obj = doc.addObject("Part::Feature", label)
    obj.Shape = solid
    group.addObject(obj)
    _apply_color(obj, color)
    return obj
