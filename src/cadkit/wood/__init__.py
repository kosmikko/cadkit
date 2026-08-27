"""Woodworking: panel joinery, cut lists, sheet nesting, cut-plan sheets.

Axes: x = width, y = depth (front->back), z = height. Parts are placed in
assembly coordinates; ``block()`` places from the min corner rather than
build123d's centred ``Box``.
"""

from cadkit.wood.cutlist import (
    DEFAULT_MARKDOWN_HEADERS,
    Part,
    markdown,
    rows,
    write_csv,
)
from cadkit.wood.cutplan_sheet import render_panel, render_parts_list
from cadkit.wood.joinery import CLEARANCE, block, dado
from cadkit.wood.nesting import Nesting, Panel, Piece, Placement, Strip, nest

__all__ = [
    "CLEARANCE",
    "DEFAULT_MARKDOWN_HEADERS",
    "Nesting",
    "Panel",
    "Part",
    "Piece",
    "Placement",
    "Strip",
    "block",
    "dado",
    "markdown",
    "nest",
    "render_panel",
    "render_parts_list",
    "rows",
    "write_csv",
]
