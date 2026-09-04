---
name: shop-drawings
description: Produce woodworking shop output with cadkit.draw and cadkit.wood — dimensioned part sheets, exploded assembly views, cut lists, sheet-goods nesting and cut plans, and multi-page A4 PDF packages. Use when a design needs drawings someone will take to the saw, when placing Dim/Callout/Detail overlays, or when assembling a PDF package.
---

# Shop drawings, cut lists and PDF packages

Not ISO drafting. Pragmatic output someone can carry to the bench:
orthographic part views with dimension lines, an exploded isometric with
labels, a cut list, and — when the piece warrants it — an A4 PDF package.

Read the `build123d` skill first if you are writing geometry; this covers
what happens after the geometry exists.

## Coordinates and conventions

- Axes: **x = width, y = depth (front→back), z = height.** Assembly origin at
  front-bottom-left. Parts are placed in **assembly coordinates** — no
  per-part local frames.
- `project_edges()` returns polylines in "view coords" (y up), **normalized so
  the geometry bbox min is at (0, 0)**. A part's face view therefore spans
  `(0..width, 0..height)`, which is why dims can be written from the same
  parameters that built the model.
- SVG y-flip happens at render time. 1 SVG user unit == 1 mm.

## The drawing API

```python
from cadkit.draw import Dim, ViewSpec, render_part_drawing, render_exploded

ViewSpec(direction, dims, caption)   # front/back/left/right/top/bottom/iso/iso_high
Dim("h"|"v", a, b, offset, label=None)   # negative offset = below/left of part
```

Dim values **auto-format from |b−a|** — pass an explicit `label` only to
override. `render_part_drawing()` lays views left-to-right on one sheet;
`render_exploded(placed, explode, path)` labels parts automatically.

`ViewSpec.callouts` — `Callout(at, to, text, anchor)` — is text with a leader
and an arrowhead to the part it names; `labels` is the same thing without the
leader. **Point `anchor` away from the leader** ("end" when the part is to the
right) or the leader runs through its own text.

`ViewSpec.details` — `Detail(centre, radius, at, scale, label, caption, dims)`
— circles a region and redraws it magnified inside a bigger circle. Both
circles come off the one projection, so a detail cannot drift from the view it
was cut from. Its dims must be `"aligned"` (a detail has no part edge for an
"h"/"v" extension line to start from) and must carry an explicit `label`,
since the geometry is magnified and the measured number would be wrong.

`view_map(shapes, view)` maps model points into the same normalized frame —
use it to derive a callout anchor or a detail centre **from the model** rather
than guessing.

## Exploded views: the rules that keep them useful

- **Labels are two rows: the part name, then its cut size** as `L×W×T` in mm —
  `f"{name}\n{dims}"` in the `labels` dict. `render_exploded` splits on the
  newline and paces rows for exactly two lines. The dimensions are the blank's
  bounding box, longest first — the same numbers the cut list quotes, so the
  exploded page can go to the saw on its own. **Never ship one labelled with
  bare part names.** An assembly iso that names parts owes the same size row,
  for the same reason.
- **Label repeated parts once, with the count.** A label of `None` draws the
  part with no text and no leader. Twelve leaders into a stack of twelve
  identical trapezoids is unreadable and says nothing the count does not —
  `board ×5 of 12` does. Every key must still be present, so a typo is still
  an error.
- **Check the view direction against the geometry.** Leaders anchor on the
  nearest point of the part's projected wireframe (not its centre, which for a
  tall thin part lands behind whatever else is there). That only helps if the
  parts are distinguishable in the projection — see the view-axis note in
  `build123d`'s `references/hlr.md` before assuming `iso` works.
- A multi-row callout runs **downward** from its anchor, which is why the
  caption is cleared past its last row.
- **Two edge columns stop working past about twenty labels on a long
  assembly** — the columns outgrow the drawing and every leader crosses it.
  `render_exploded(..., layout="near", groups={part: group})` places each
  label on a lattice slot in the free space next to its part instead, most
  constrained part first, then moves and swaps labels until no leader
  shortens; `groups` clusters one sub-assembly's labels together. Labels
  never overlap a part's outline or another label and a leader never runs
  through text; a leader crossing another part or another leader only costs
  score. The default `layout="columns"` is unchanged and right for a sheet
  of a dozen parts.

## Cut lists and nesting

```python
from cadkit.wood import Part, block, dado, nest, render_panel, write_csv
```

`Part(name, shape, qty, material, note)` takes panel dims from the bounding
box, sorted descending — joinery cuts do not change the blank, so the bbox is
the right source for stock. `Design.cutlist()` declares the CSV.

`nest(pieces, panel_length, panel_width, kerf)` packs parts onto sheet goods;
`render_panel` and `render_parts_list` draw the resulting cut plan.

## PDF packages

`cadkit.draw.PdfReport` composes A4 pages (landscape or portrait — an exploded
view of a tall module is about 3:4, and landscape wastes half the sheet).
`place_svg` embeds a drawing **as vector content** and stamps an invisible
`DRAWING_ID:` marker so a test can assert which drawing landed on which page.

A PDF package requires automated tests for: page count, exact A4 page size,
extractable content, manifest completeness, and source-artifact associations.
Preserve vector sources as vector unless the design explicitly approves
raster.

Use PyMuPDF for cross-platform, all-page rendering — **not** Quick Look, which
only ever renders the first page. Non-ASCII text needs the bundled FiraGO font
(`pymupdf.Font("figo")`, already the `PdfReport` default): Helvetica does not
round-trip an en dash.

Render **every** PDF page to PNG and inspect it before calling the package
done. During iteration, the `cad-iterate` skill's visual diff decides which
pages actually need looking at.
