"""
cellpacker.geometry.grid
~~~~~~~~~~~~~~~~~~~~~~~~
Hexagonal close-packed grid generation.

The grid is computed in a *rotated* coordinate frame so that rows can be
aligned to any angle.  Candidate positions are back-transformed into the
sketch's local coordinate system before the containment check.
"""

import math
from typing import NamedTuple

from cellpacker.geometry.transforms import rotate_2d, inverse_rotate_2d
from cellpacker.geometry.face import circle_fits


class GridParams(NamedTuple):
    """Derived grid parameters computed from cell diameter and clearance."""
    pitch_x: float   # centre-to-centre distance along a row
    pitch_y: float   # centre-to-centre distance between rows (hex packing)
    radius: float    # cell radius used for containment checks


def grid_params_from_config(cfg: dict) -> GridParams:
    """Compute :class:`GridParams` from a configuration dict."""
    radius = cfg["cell_diameter"] / 2.0
    pitch_x = cfg["cell_diameter"] + cfg["clearance"]
    pitch_y = pitch_x * math.sqrt(3) / 2.0
    return GridParams(pitch_x=pitch_x, pitch_y=pitch_y, radius=radius)


def generate_candidate_points(
    face,
    bbox,
    angle_deg: float,
    params: GridParams,
) -> list[tuple[float, float]]:
    """
    Generate all cell-centre positions (in **local** sketch coordinates)
    that fit inside *face* when the hex grid is rotated by *angle_deg*.

    Parameters
    ----------
    face:
        ``Part.Face`` in local sketch coordinates.
    bbox:
        ``BoundBox`` of *face* (``face.BoundBox``).
    angle_deg:
        Grid rotation angle in degrees.
    params:
        Pre-computed :class:`GridParams`.

    Returns
    -------
    list of (x, y) tuples in local sketch coordinates.
    """
    px, py, r = params.pitch_x, params.pitch_y, params.radius

    # Compute rotated bounding box to know how far to sweep
    corners = [
        (bbox.XMin, bbox.YMin),
        (bbox.XMin, bbox.YMax),
        (bbox.XMax, bbox.YMin),
        (bbox.XMax, bbox.YMax),
    ]
    rcorners = [rotate_2d(x, y, angle_deg) for x, y in corners]
    min_rx = min(c[0] for c in rcorners) - px
    max_rx = max(c[0] for c in rcorners) + px
    min_ry = min(c[1] for c in rcorners) - py
    max_ry = max(c[1] for c in rcorners) + py

    points: list[tuple[float, float]] = []
    row_idx = 0
    ry = min_ry
    while ry <= max_ry:
        x_offset = 0.0 if row_idx % 2 == 0 else px / 2.0
        rx = min_rx + x_offset
        while rx <= max_rx:
            lx, ly = inverse_rotate_2d(rx, ry, angle_deg)
            if circle_fits(face, lx, ly, r):
                points.append((lx, ly))
            rx += px
        ry += py
        row_idx += 1

    return points
