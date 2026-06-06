"""
cellpacker.drawing.colors
~~~~~~~~~~~~~~~~~~~~~~~~~
Color helpers for series-group visualisation.
"""

import colorsys


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[float, float, float]:
    """Convert HSV (all in [0, 1]) to an RGB triple of floats."""
    return tuple(float(c) for c in colorsys.hsv_to_rgb(h, s, v))  # type: ignore[return-value]


def get_series_color(
    series_idx: int,
    total_series: int,
) -> tuple[float, float, float]:
    """
    Return an RGB color for *series_idx* (1-based) out of *total_series*.

    Uses the golden-ratio hue step (~137.5° per step) so adjacent series
    groups always land on maximally separated hues regardless of pack size.
    """
    _GOLDEN = 0.6180339887498949
    h = (series_idx * _GOLDEN) % 1.0
    return hsv_to_rgb(h, 0.72, 0.92)
