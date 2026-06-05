"""
cellpacker.utils
~~~~~~~~~~~~~~~~
Small shared utilities that don't belong to any specific sub-domain.
"""

from __future__ import annotations


def parse_float_list(text: str | None, fallback: list[float]) -> list[float]:
    """
    Parse a comma-separated string of floats.

    Returns *fallback* if *text* is empty or unparseable.
    """
    text = (text or "").strip()
    if not text:
        return list(fallback)
    vals: list[float] = []
    for part in text.split(","):
        part = part.strip()
        if part:
            try:
                vals.append(float(part))
            except ValueError:
                pass
    return vals if vals else list(fallback)


def ensure_active_doc():
    """Return the active FreeCAD document or raise RuntimeError."""
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("No active FreeCAD document.")
    return doc
