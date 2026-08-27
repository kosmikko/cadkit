"""Geometry helpers for panel furniture.

Convention: block() uses min-corner placement (like laying parts out from
the front-bottom-left origin), which reads better for furniture than
build123d's center-origin Box.

Axes: x = width, y = depth (front->back), z = height.
"""

from build123d import Box, Pos

#: Fit clearance added to dado/groove widths so parts slide together.
CLEARANCE = 0.2


def block(w: float, d: float, h: float, at=(0, 0, 0)):
    """Axis-aligned box with its min corner at `at`. Panels and cutters alike."""
    x, y, z = at
    return Pos(x + w / 2, y + d / 2, z + h / 2) * Box(w, d, h)


def dado(panel, *, width: float, depth: float, at, along: str = "y",
         length: float | None = None, clearance: float = CLEARANCE):
    """Cut a dado (rectangular groove) into a panel; returns the cut panel.

    width:  nominal width of the mating part (clearance is added here).
    depth:  groove depth, cut inward from the face the groove starts at.
    at:     min corner of the groove volume (before clearance), in model coords.
    along:  axis the groove runs along ("x" or "y"); it runs the panel's
            full extent on that axis unless `length` is given.
    """
    bb = panel.bounding_box()
    x, y, z = at
    w = width + clearance
    if along == "y":
        run = length if length is not None else (bb.max.Y - bb.min.Y)
        cutter = block(depth, run, w, at=(x, y, z - clearance / 2))
    elif along == "x":
        run = length if length is not None else (bb.max.X - bb.min.X)
        cutter = block(run, depth, w, at=(x, y, z - clearance / 2))
    else:
        raise ValueError(f"along must be 'x' or 'y', got {along!r}")
    return panel - cutter
