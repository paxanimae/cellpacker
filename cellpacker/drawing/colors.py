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

    Uses a full hue rotation so neighbouring series groups have distinct
    colors even for large packs.
    """
    if total_series <= 1:
        return (0.8, 0.2, 0.2)
    h = float(series_idx - 1) / float(total_series)
    return hsv_to_rgb(h, 0.65, 0.95)
