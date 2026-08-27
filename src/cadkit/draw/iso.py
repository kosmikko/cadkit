"""The cheap shape check: one isometric SVG, no dimensions, no sheet.

3D printing does not need shop drawings — it needs to see that the thing it
just modelled is the thing it meant to model. This is the shortest path
through the same projection and the same SVG writer that the dimensioned
drawings use, so the HLR gotchas are fixed in exactly one place.
"""

from cadkit.draw.drawing import SvgSheet, project_edges

#: Matches preview output from before the projection code was unified.
MARGIN = 8.0


def iso(part, path, view="iso", *, margin: float = MARGIN):
    """Write an isometric wireframe of `part` to `path`; returns `path`.

    `view` is any VIEW_DIRS name ("iso", "iso_high", "front", "top", ...) or a
    direction Vector. Hidden edges are drawn dashed, as on the part sheets.
    """
    visible, hidden = project_edges(part, view)
    sheet = SvgSheet()
    sheet.add_polys(hidden, "hidden")
    sheet.add_polys(visible, "visible")
    sheet.render(path, margin=margin)
    return path
