"""Shop drawings and previews: HLR projection to SVG.

One projection implementation serves everything here — dimensioned part
sheets, exploded assembly views, and the cheap ``iso()`` shape check that
3D printing uses instead of drawings.
"""

from cadkit.draw.drawing import (
    CAMERA_DIST,
    STYLES,
    TEXT_SIZE,
    VIEW_DIRS,
    Callout,
    Detail,
    Dim,
    SvgSheet,
    ViewSpec,
    project_edges,
    render_exploded,
    render_part_drawing,
    sheet_text_scale,
    view_basis,
    view_map,
)
from cadkit.draw.iso import iso
from cadkit.draw.pdf_report import (
    A4_LANDSCAPE_MM,
    A4_PORTRAIT_MM,
    MM_TO_PT,
    PdfReport,
    mm,
    rect_mm,
)

__all__ = [
    "A4_LANDSCAPE_MM",
    "A4_PORTRAIT_MM",
    "CAMERA_DIST",
    "MM_TO_PT",
    "STYLES",
    "TEXT_SIZE",
    "VIEW_DIRS",
    "Callout",
    "Detail",
    "Dim",
    "PdfReport",
    "SvgSheet",
    "ViewSpec",
    "iso",
    "mm",
    "project_edges",
    "rect_mm",
    "render_exploded",
    "render_part_drawing",
    "sheet_text_scale",
    "view_basis",
    "view_map",
]
