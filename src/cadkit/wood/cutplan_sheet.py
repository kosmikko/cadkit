"""Cut-plan sheets: a nested panel beside its key, and a plain parts list.

Both are drawn straight into `SvgSheet` in millimetres of real panel, so the
PDF can scale them like any other drawing. Sizes here are therefore panel mm,
not paper mm: TEXT is ~30 on a 1525 sheet, which lands near 2 mm on the page.

Parts carry an **index, not a name**. A 550 x 50 drawer front is a sliver 50 mm
along the strip; no horizontal label fits in it, and rotating text for the
narrow ones and not the wide ones reads as a mistake rather than a decision.
Numbering every part and putting the names in a key beside the panel is what a
cut plan does anyway, and the key doubles as that panel's own cut list.
"""

from __future__ import annotations

from cadkit.draw.drawing import SvgSheet

TEXT = 30.0
TITLE_TEXT = 44.0
ROW_STEP = 40.0
KEY_GAP = 90.0
#: Index numbers shrink to fit their part but stay legible.
INDEX_MIN = 15.0
INDEX_MAX = 46.0

PANEL_STYLE = "visible"
PART_STYLE = "visible"
WASTE_STYLE = "hidden"


def _rect(sheet, x, y, w, h, style):
    sheet.add_polys(
        [[(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]], style
    )


def _fmt(value: float) -> str:
    return f"{round(value, 1):g}"


def render_panel(nesting, index, path, *, title, sizes) -> None:
    """One nested panel: the sheet to scale, then its key to the right.

    `sizes` maps a part name to the cut size string shown in the key, so the
    numbers here are the cut list's own and cannot drift from it.
    """
    panel = nesting.panels[index]
    length, width = nesting.panel_length, nesting.panel_width
    sheet = SvgSheet()

    # The panel itself. y is drawn up, so the sheet reads with x along its
    # length — strips are horizontal bands and every part label is horizontal.
    _rect(sheet, 0, 0, length, width, PANEL_STYLE)

    rows = []
    for number, placement in enumerate(panel.placements, start=1):
        _rect(sheet, placement.x, placement.y, placement.length, placement.width,
              PART_STYLE)
        size = min(placement.length, placement.width) * 0.55
        size = max(INDEX_MIN, min(INDEX_MAX, size))
        sheet.text(
            placement.x + placement.length / 2,
            placement.y + placement.width / 2 - size * 0.35,
            str(number),
            size=size,
        )
        rows.append((number, placement.name))

    sheet.text(length / 2, width + TITLE_TEXT * 0.8, title, size=TITLE_TEXT)

    key_x = length + KEY_GAP
    top = width - TEXT
    used = sum(p.area for p in panel.placements)
    sheet.text(key_x, top, f"panel {index + 1}  ·  {_fmt(length)} × {_fmt(width)}"
               f"  ·  {used / (length * width) * 100:.0f}% used",
               size=TEXT, anchor="start")
    for offset, (number, name) in enumerate(rows, start=2):
        sheet.text(key_x, top - offset * ROW_STEP,
                   f"{number}   {name}   {sizes[name]}",
                   size=TEXT, anchor="start")
    rips = max(0, len(panel.strips) - 1)
    crosscuts = len(panel.placements)
    sheet.text(key_x, top - (len(rows) + 3) * ROW_STEP,
               f"{rips} rips, then {crosscuts} crosscuts",
               size=TEXT, anchor="start")
    sheet.render(path, margin=40.0)


def render_parts_list(path, *, title, columns, rows, notes=()) -> None:
    """A plain table — no drawing — for parts this package does not nest."""
    sheet = SvgSheet()
    # Column x positions are set by the widest cell, so nothing runs into the
    # next column; the row height is fixed, so a long note wraps by being
    # split at the caller rather than by overprinting.
    widths = [
        max(0.62 * TEXT * len(str(cell)) for cell in (header, *(r[i] for r in rows)))
        for i, header in enumerate(columns)
    ]
    xs, cursor = [], 0.0
    for column_width in widths:
        xs.append(cursor)
        cursor += column_width + 0.62 * TEXT * 4
    total = cursor

    top = 0.0
    sheet.text(0, top + TITLE_TEXT * 1.6, title, size=TITLE_TEXT, anchor="start")
    for x, header in zip(xs, columns, strict=True):
        sheet.text(x, top, header, size=TEXT, anchor="start")
    sheet.line(0, top - ROW_STEP * 0.35, total, top - ROW_STEP * 0.35, "dim")
    for index, row in enumerate(rows, start=1):
        y = top - index * ROW_STEP
        for x, cell in zip(xs, row, strict=True):
            sheet.text(x, y, str(cell), size=TEXT, anchor="start")
    # a clear row between the table and the notes: SVG collapses leading
    # spaces, so indentation cannot do the separating
    y = top - (len(rows) + 2) * ROW_STEP
    for offset, note in enumerate(notes):
        sheet.text(0, y - offset * ROW_STEP, note, size=TEXT, anchor="start")
    sheet.render(path, margin=40.0)
