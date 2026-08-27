# Hidden-line removal and view frames

`shape.project_to_viewport(camera, viewport_up=...)` does the hidden-line
removal and returns `(visible, hidden)` edge lists **already planar** (z=0).
`cadkit.draw.project_edges(shape, view)` wraps it with the settings below;
prefer that over calling the raw method.

## Put the camera far away

Projection is **perspective**, not orthographic. `cadkit.draw.CAMERA_DIST` is
`100_000.0` mm, which puts the error around 1e-4 and the scale at 1:1. At a
half-metre camera distance an 18 mm panel projects as 18.04 mm.

## Geometry far from the origin still shows perspective

The camera sits `CAMERA_DIST` along the view direction **from the origin**,
not from the shape. A part at x 1850–2400 therefore has its near and far
faces projected about 10 mm apart in a 550-wide front view — invisible at
1:1, glaring the moment a detail view magnifies it.

Centre the shape before drawing it magnified (`ViewSpec(shape=...)`). It
costs nothing, because every projection is normalized to its own bounding box
anyway. Raising `CAMERA_DIST` would fix it globally, at the price of
regenerating every SVG in every design.

`tests/test_iso.py::test_geometry_far_from_the_origin_shows_perspective`
pins the actual size of the error.

## HLR output is self-centered per call

Two separate projections do **not** share a 2D frame — each is normalized to
its own bounding box. Consequences:

- To draw several parts in one frame, project the whole `Compound` at once.
  Projecting them separately and overlaying the results silently misaligns
  them.
- To map a 3D anchor point into a projected view (for a callout, a detail
  centre, a leader), use an orthographic basis plus bbox-min alignment:
  `cadkit.draw.view_basis(view)` gives `(right, up)`, and
  `cadkit.draw.view_map(shapes, view)` does the whole mapping. Derive anchors
  from the model this way rather than guessing coordinates.

## Do not negate the right vector

In `view_basis`: `right = forward.cross(up)` — **do not negate it**. Negating
flips the frame 180°, which lands every label on the wrong part. This has
been debugged once already; the vision check is what caught it, not a test.

## View directions

`cadkit.draw.VIEW_DIRS` holds front/back/left/right/top/bottom/iso/iso_high.
Anything else can be passed as a direction `Vector` to `project_edges`,
`view_basis` or `iso`.

The screen-horizontal axis is a horizontal vector perpendicular to the view
direction. So `iso` = (1, -1, 0.8) resolves to **(x + y)**: any two parts
sharing an `x + y` sum project on top of each other. `iso_high` = (1, 1, 1.6)
runs it along **(y - x)** and looks further down, which separates those parts
and shows plan-shaped parts as their actual outline. Compute the spread
before assuming a view works.
