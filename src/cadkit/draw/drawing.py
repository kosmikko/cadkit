"""Shop-drawing generation: HLR projections + dimension overlays -> SVG.

Not ISO drafting. Pragmatic output: per-part orthographic views with
dimension lines, and an exploded isometric assembly view with labels.

Coordinate conventions:
- Model space is mm; z up.
- project_edges() returns planar polylines in "view coords" (y up),
  normalized so the geometry bbox min is at (0, 0).
- Dims are specified in those normalized view coords, so a part's face
  view spans (0..width, 0..height) and callers can place dims from the
  same parameters that built the model.
- SVG y-flip is handled at render time; 1 SVG user unit == 1 mm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from build123d import Compound, GeomType, Vector

CAMERA_DIST = 100_000.0  # far camera => perspective error ~1e-4, scale is 1:1

VIEW_DIRS = {
    "front": Vector(0, -1, 0),
    "back": Vector(0, 1, 0),
    "left": Vector(-1, 0, 0),
    "right": Vector(1, 0, 0),
    "top": Vector(0, 0, 1),
    "bottom": Vector(0, 0, -1),
    "iso": Vector(1, -1, 0.8),
    # A steeper iso from the other side. "iso" puts the screen-horizontal axis
    # along (x + y), so any two parts sharing an x + y sum land on top of each
    # other; this one runs it along (y - x) and looks further down, which both
    # separates them and shows plan-shaped parts as their actual outline.
    "iso_high": Vector(1, 1, 1.6),
}
VIEW_UPS = {"top": Vector(0, 1, 0), "bottom": Vector(0, -1, 0)}


def sheet_text_scale(span: float, panel_mm: float, target_mm: float = 2.6) -> float:
    """Text multiplier that lands ~`target_mm` of type on the printed page.

    ``render_part_drawing`` draws its annotations at :data:`TEXT_SIZE` mm *of
    model*, and a sheet placed in a PDF panel is then scaled to fit it. A
    drawing of a 1 500 mm rack in a 184 mm panel therefore prints its labels at
    a third of a millimetre unless the type is sized from that same ratio.

    `span` is the drawing's largest extent in model mm, `panel_mm` the printed
    width of the panel it lands in.
    """
    if not (span > 0 and panel_mm > 0 and target_mm > 0):
        raise ValueError("span, panel_mm and target_mm must all be positive")
    return span / panel_mm * target_mm / TEXT_SIZE


def view_direction(view) -> Vector:
    """Camera direction for a named view, or an explicit direction vector."""
    return VIEW_DIRS[view] if isinstance(view, str) else Vector(view)


def _up(view) -> Vector:
    if not isinstance(view, str):
        return Vector(0, 0, 1)
    return VIEW_UPS.get(view, Vector(0, 0, 1))


def _polylines(edges, curve_segments: int = 24) -> list[list[tuple[float, float]]]:
    out = []
    for e in edges:
        n = 1 if e.geom_type == GeomType.LINE else curve_segments
        pts = []
        for i in range(n + 1):
            p = e @ (i / n)
            pts.append((p.X, p.Y))
        out.append(pts)
    return out


def _bounds(polys):
    xs = [x for pl in polys for x, _ in pl]
    ys = [y for pl in polys for _, y in pl]
    return min(xs), min(ys), max(xs), max(ys)


def _shift(polys, dx, dy):
    return [[(x + dx, y + dy) for x, y in pl] for pl in polys]


def _scale_polys(polys, scale):
    return [[(x * scale, y * scale) for x, y in pl] for pl in polys]


def project_edges(shape, view):
    """HLR-project shape; returns (visible, hidden) polylines normalized to origin.

    `view` is a name from VIEW_DIRS, or a direction Vector for a one-off angle.
    """
    cam = tuple(view_direction(view).normalized() * CAMERA_DIST)
    visible, hidden = shape.project_to_viewport(cam, viewport_up=tuple(_up(view)))
    vis, hid = _polylines(visible), _polylines(hidden)
    x0, y0, _, _ = _bounds(vis + hid)
    return _shift(vis, -x0, -y0), _shift(hid, -x0, -y0)


def view_basis(view):
    """Orthographic basis (right, up) for mapping 3D points into view coords.

    Matches project_to_viewport's frame up to a constant offset (HLR output is
    self-centered per call, so align via bbox before use).
    """
    forward = -view_direction(view).normalized()
    right = forward.cross(_up(view)).normalized()
    up = right.cross(forward).normalized()
    return right, up


@dataclass
class Dim:
    """A linear dimension in normalized view coords.

    kind "h": measures x distance a..b, dim line at y=offset.
    kind "v": measures y distance a..b, dim line at x=offset.
    kind "aligned": measures between 2D point endpoints a and b, with the
    dimension line offset perpendicular to the measured segment.
    Negative offset puts the dim below / left of the part.
    """

    kind: str
    a: float | tuple[float, float]
    b: float | tuple[float, float]
    offset: float
    label: str | None = None


@dataclass
class Callout:
    """Text on a view with a leader to the part it names.

    `at` is where the text sits and where the leader starts; `to` is the point
    on the part the arrowhead lands on. Both in the same normalized view coords
    the dimensions use. Text splits on "\\n" and runs downward, like an exploded
    view's labels.

    `anchor` should face the text *away* from the leader — "end" when the part
    is to the right of the text, "start" when it is to the left — or the leader
    is drawn straight through its own label.
    """

    at: tuple[float, float]
    to: tuple[float, float]
    text: str
    anchor: str = "start"


@dataclass
class Detail:
    """A round, magnified view of one region of the same projection.

    The drafting convention: a thin circle round the feature on the view with
    a letter beside it, and the same circle redrawn larger where there is room
    for it. Both come off the one projection, so the detail cannot drift from
    the view it is cut out of — no second solid, no second alignment.

    centre / radius: the region, in the normalized view coords the dims use.
    at:              where the magnified circle's centre goes, same coords.
    scale:           magnification; the drawn circle is `radius * scale`.
    label:           the letter beside the region on the view.
    caption:         text under the magnified circle; splits on "\\n".
    dims:            dimensions of the magnified geometry. They are carried
                     through the same transform as the geometry, so give them
                     in region coords and label them with the real size —
                     "aligned" only, because a detail has no part edges for an
                     "h" or "v" dim's extension lines to start from.
    """

    centre: tuple[float, float]
    radius: float
    at: tuple[float, float]
    scale: float
    label: str = "A"
    caption: str | None = None
    dims: list[Dim] = field(default_factory=list)


@dataclass
class ViewSpec:
    direction: str
    dims: list[Dim] = field(default_factory=list)
    show_hidden: bool = True
    caption: str | None = None
    shape: object | None = None
    presentation_scale: float = 1.0
    dimension_offset_scale: float | None = None
    vertical_dimension_offset_scale: float | None = None
    dimension_text_scale: float = 1.0
    # Label for a north arrow drawn beside the view, e.g. "P" on a Finnish
    # plan.  Only meaningful on a view whose up direction is a compass
    # bearing, which for "top" and "bottom" is model +Y and -Y.
    compass: str | None = None
    # Free annotations as ((x, y), text) in the same normalized view coords the
    # dimensions use: the part spans (0..w, 0..h).  Drawn at the dimension text
    # size, left-anchored on the point.
    labels: list[tuple[tuple[float, float], str]] = field(default_factory=list)
    # Named parts and magnified joints, both in the same normalized view coords.
    callouts: list[Callout] = field(default_factory=list)
    details: list[Detail] = field(default_factory=list)


STYLES = {
    "visible": 'fill="none" stroke="#111" stroke-width="0.5"',
    "hidden": 'fill="none" stroke="#999" stroke-width="0.3" stroke-dasharray="2,1.5"',
    "dim": 'fill="none" stroke="#555" stroke-width="0.25"',
    "leader": 'fill="none" stroke="#555" stroke-width="0.35"',
}
TEXT_SIZE = 3.5
ARROW_LEN = 2.5
ARROW_HALF = 0.8
COMPASS_LEN = 14.0
COMPASS_GAP = 12.0
EXPLODED_LABEL_MIN = 32.0
EXPLODED_LABEL_MAX = 64.0
EXPLODED_LABEL_SCALE = 250.0
EXPLODED_COLUMN_GAP = 12.0
EXPLODED_ROW_GAP = 1.5
#: layout="near" scoring, all in label sizes: a label joins its group's
#: cluster if that costs less than this much extra leader; lining up with a
#: clustered label is worth a little more; every other part and every earlier
#: leader the leader crosses costs this much. CHAR_W matches SvgSheet._bbox.
EXPLODED_CHAR_W = 0.62
EXPLODED_NEAR_COHESION = 6.0
EXPLODED_NEAR_ALIGN = 1.5
EXPLODED_NEAR_CROSS_PART = 2.0
EXPLODED_NEAR_CROSS_LEADER = 1.5
EXPLODED_NEAR_CANDIDATES = 48  # nearest usable slots scored per label
EXPLODED_NEAR_POOL = 60  # nearest slots counted to rank how boxed-in a label is
EXPLODED_NEAR_PASSES = 8  # improvement rounds of moves and swaps
EXPLODED_NEAR_MIN_GAIN = 0.5  # in sizes; smaller gains are not worth the churn
EXPLODED_NEAR_REACH = 2  # lattice extends this many label pitches past the drawing


class SvgSheet:
    """Accumulates primitives in math coords (y up), renders flipped SVG."""

    def __init__(self):
        self.polys: list[tuple[list[tuple[float, float]], str]] = []
        self.texts: list[tuple[float, float, str, float, str]] = []
        # x, y, angle (rad), size scale
        self.arrows: list[tuple[float, float, float, float]] = []

    def add_polys(self, polys, style):
        for pl in polys:
            self.polys.append((pl, style))

    def line(self, x1, y1, x2, y2, style="dim"):
        self.polys.append(([(x1, y1), (x2, y2)], style))

    def circle(self, cx, cy, radius, style="dim", segments=72):
        """A circle as a closed polyline, so it needs no new render path."""
        step = 2 * math.pi / segments
        self.polys.append((
            [
                (cx + radius * math.cos(i * step), cy + radius * math.sin(i * step))
                for i in range(segments + 1)
            ],
            style,
        ))

    def text(self, x, y, s, size=TEXT_SIZE, anchor="middle"):
        self.texts.append((x, y, s, size, anchor))

    def arrow(self, x, y, angle, scale=1.0):
        """Filled arrowhead with tip at (x, y) pointing along angle.

        `scale` multiplies the head size. Dimension arrows are drawn against
        3.5 mm text; a sheet whose labels are ten times that needs heads to
        match or they vanish.
        """
        self.arrows.append((x, y, angle, scale))

    def _bbox(self):
        xs, ys = [], []
        for pl, _ in self.polys:
            for x, y in pl:
                xs.append(x)
                ys.append(y)
        for x, y, s, size, anchor in self.texts:
            w = 0.62 * size * len(s)
            x0 = {"middle": x - w / 2, "start": x, "end": x - w}[anchor]
            xs += [x0, x0 + w]
            ys += [y - size * 0.4, y + size * 0.8]
        for x, y, _, _ in self.arrows:
            xs.append(x)
            ys.append(y)
        return min(xs), min(ys), max(xs), max(ys)

    def render(self, path, margin=10.0):
        x0, y0, x1, y1 = self._bbox()
        w, h = x1 - x0 + 2 * margin, y1 - y0 + 2 * margin

        def tx(x):
            return round(x - x0 + margin, 2)

        def ty(y):
            return round(y1 - y + margin, 2)  # flip: math y-up -> svg y-down

        el = []
        for pl, style in self.polys:
            pts = " ".join(f"{tx(x)},{ty(y)}" for x, y in pl)
            el.append(f'<polyline points="{pts}" {STYLES[style]}/>')
        for x, y, ang, scale in self.arrows:
            # triangle: tip + two base corners, angle in math coords
            c, s = math.cos(ang), math.sin(ang)
            length, half = ARROW_LEN * scale, ARROW_HALF * scale
            bx, by = x - length * c, y - length * s
            px, py = -s * half, c * half
            p = (
                f"M {tx(x)},{ty(y)} L {tx(bx + px)},{ty(by + py)} "
                f"L {tx(bx - px)},{ty(by - py)} Z"
            )
            el.append(f'<path d="{p}" fill="#555" stroke="none"/>')
        for x, y, s_, size, anchor in self.texts:
            el.append(
                f'<text x="{tx(x)}" y="{ty(y)}" font-size="{size}" '
                f'font-family="Helvetica, Arial, sans-serif" fill="#111" '
                f'text-anchor="{anchor}">{escape(s_)}</text>'
            )
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}mm" '
            f'height="{h:.0f}mm" viewBox="0 0 {w:.2f} {h:.2f}">\n'
            + "\n".join(el)
            + "\n</svg>\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)


def _fmt(v: float) -> str:
    return f"{round(v, 1):g}"


def _scale_dim(
    d: Dim, scale: float, offset_scale: float, vertical_offset_scale: float
) -> Dim:
    if d.kind == "aligned":
        ax, ay = d.a
        bx, by = d.b
        label = d.label or _fmt(math.hypot(bx - ax, by - ay))
        return Dim(
            d.kind,
            (ax * scale, ay * scale),
            (bx * scale, by * scale),
            d.offset * offset_scale,
            label,
        )
    return Dim(
        d.kind,
        d.a * scale,
        d.b * scale,
        d.offset * (vertical_offset_scale if d.kind == "v" else offset_scale),
        d.label or _fmt(abs(d.b - d.a)),
    )


def _draw_dim(
    sheet: SvgSheet,
    d: Dim,
    vw: float,
    vh: float,
    ox: float,
    oy: float,
    text_scale: float = 1.0,
):
    ext_gap, ext_over = 1.0, 1.5
    if d.kind == "aligned":
        ax, ay = d.a
        bx, by = d.b
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        side = 1 if d.offset >= 0 else -1
        start = (ox + ax, oy + ay)
        end = (ox + bx, oy + by)
        dim_start = (
            start[0] + nx * d.offset,
            start[1] + ny * d.offset,
        )
        dim_end = (
            end[0] + nx * d.offset,
            end[1] + ny * d.offset,
        )
        sheet.line(
            start[0] + nx * side * ext_gap,
            start[1] + ny * side * ext_gap,
            dim_start[0] + nx * side * ext_over,
            dim_start[1] + ny * side * ext_over,
        )
        sheet.line(
            end[0] + nx * side * ext_gap,
            end[1] + ny * side * ext_gap,
            dim_end[0] + nx * side * ext_over,
            dim_end[1] + ny * side * ext_over,
        )
        sheet.line(*dim_start, *dim_end)
        angle = math.atan2(uy, ux)
        sheet.arrow(*dim_start, angle + math.pi)
        sheet.arrow(*dim_end, angle)
        sheet.text(
            (dim_start[0] + dim_end[0]) / 2 + nx * side * 1.2,
            (dim_start[1] + dim_end[1]) / 2 + ny * side * 1.2,
            d.label or _fmt(length),
            size=TEXT_SIZE * text_scale,
        )
        return

    lo, hi = min(d.a, d.b), max(d.a, d.b)
    label = d.label or _fmt(hi - lo)
    if d.kind == "h":
        y = oy + d.offset
        base = oy if d.offset < vh / 2 else oy + vh  # nearest part edge
        sgn = 1 if y >= base else -1
        for x in (lo, hi):
            sheet.line(ox + x, base + sgn * ext_gap, ox + x, y + sgn * ext_over)
        sheet.line(ox + lo, y, ox + hi, y)
        sheet.arrow(ox + lo, y, math.pi)
        sheet.arrow(ox + hi, y, 0)
        sheet.text(ox + (lo + hi) / 2, y + 1.2, label, size=TEXT_SIZE * text_scale)
    else:
        x = ox + d.offset
        base = ox if d.offset < vw / 2 else ox + vw
        sgn = 1 if x >= base else -1
        for yy in (lo, hi):
            sheet.line(base + sgn * ext_gap, oy + yy, x + sgn * ext_over, oy + yy)
        sheet.line(x, oy + lo, x, oy + hi)
        sheet.arrow(x, oy + lo, -math.pi / 2)
        sheet.arrow(x, oy + hi, math.pi / 2)
        side = -1 if d.offset < vw / 2 else 1
        sheet.text(
            x + side * 1.5, oy + (lo + hi) / 2 - 1.2, label,
            size=TEXT_SIZE * text_scale,
            anchor="end" if side < 0 else "start",
        )


def _segment_in_circle(a, b, cx, cy, radius):
    """The part of segment a..b inside the circle, as (start, end) or None."""
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    fx, fy = ax - cx, ay - cy
    qa = dx * dx + dy * dy
    if qa == 0:
        return (a, b) if math.hypot(fx, fy) <= radius else None
    qb = 2 * (fx * dx + fy * dy)
    qc = fx * fx + fy * fy - radius * radius
    disc = qb * qb - 4 * qa * qc
    if disc <= 0:
        return None
    root = math.sqrt(disc)
    t0 = max(0.0, (-qb - root) / (2 * qa))
    t1 = min(1.0, (-qb + root) / (2 * qa))
    if t1 <= t0:
        return None
    return (
        (ax + t0 * dx, ay + t0 * dy),
        (ax + t1 * dx, ay + t1 * dy),
    )


def _clip_to_circle(polys, cx, cy, radius):
    """Whatever of `polys` falls inside the circle, as new polylines."""
    out = []
    for pl in polys:
        run = []
        for a, b in zip(pl, pl[1:]):
            piece = _segment_in_circle(a, b, cx, cy, radius)
            if piece is None:
                if len(run) > 1:
                    out.append(run)
                run = []
                continue
            start, end = piece
            if run and run[-1] == start:
                run.append(end)
            else:
                if len(run) > 1:
                    out.append(run)
                run = [start, end]
        if len(run) > 1:
            out.append(run)
    return out


def view_map(shapes, view: str):
    """Map model points into the normalized 2D frame of a view of `shapes`.

    project_edges() normalizes every projection to its own bbox min, and HLR
    output is self-centered per call, so anything placed on a view from model
    coordinates — a leader anchor, the centre of a detail circle — has to be
    projected with the same orthographic basis and then aligned the same way.
    Returns a callable taking a point (or a Vector) to (x, y) in view coords.

    Accurate to the projection's perspective error, which grows with how far
    the geometry sits off the camera axis; see CAMERA_DIST.
    """
    right, up = view_basis(view)
    corners = []
    for shape in shapes:
        bb = shape.bounding_box()
        corners += [
            Vector(x, y, z)
            for x in (bb.min.X, bb.max.X)
            for y in (bb.min.Y, bb.max.Y)
            for z in (bb.min.Z, bb.max.Z)
        ]
    if not corners:
        raise ValueError("view_map needs at least one shape")
    x0 = min(corner.dot(right) for corner in corners)
    y0 = min(corner.dot(up) for corner in corners)

    def to_view(point):
        vector = point if isinstance(point, Vector) else Vector(*point)
        return (vector.dot(right) - x0, vector.dot(up) - y0)

    return to_view


#: Baseline-to-baseline spacing of a callout's rows, in text sizes. Shared with
#: the caption clearance, so a label's last row cannot be paced onto the
#: caption's line.
_CALLOUT_LINE_STEP = 1.3


def _draw_callout(sheet: SvgSheet, callout: Callout, ox, oy, scale, size):
    ax, ay = ox + callout.at[0] * scale, oy + callout.at[1] * scale
    tx, ty = ox + callout.to[0] * scale, oy + callout.to[1] * scale
    sheet.line(ax, ay, tx, ty, "leader")
    # Scaled to the text, as in render_exploded: a 2.5 mm head against a label
    # ten times that is a leader that appears to stop nowhere in particular.
    sheet.arrow(tx, ty, math.atan2(ty - ay, tx - ax), scale=size / (TEXT_SIZE * 2))
    for index, line in enumerate(callout.text.split("\n")):
        sheet.text(ax, ay - index * size * _CALLOUT_LINE_STEP, line, size=size,
                   anchor=callout.anchor)


def _draw_detail(sheet: SvgSheet, detail: Detail, vis, hid, ox, oy, scale,
                 size, show_hidden: bool):
    """Circle the region on the view, then redraw it magnified beside itself."""
    cx, cy = detail.centre[0] * scale, detail.centre[1] * scale
    radius = detail.radius * scale
    ax, ay = detail.at[0] * scale, detail.at[1] * scale
    magnification = detail.scale

    def magnify(point):
        return (
            ax + (point[0] - cx) * magnification,
            ay + (point[1] - cy) * magnification,
        )

    sheet.circle(ox + cx, oy + cy, radius)
    sheet.text(ox + cx + radius + size * 0.4, oy + cy + radius * 0.5,
               detail.label, size=size, anchor="start")

    layers = [(vis, "visible")] + ([(hid, "hidden")] if show_hidden else [])
    for polys, style in layers:
        sheet.add_polys(
            [
                [(ox + x, oy + y) for x, y in map(magnify, pl)]
                for pl in _clip_to_circle(polys, cx, cy, radius)
            ],
            style,
        )
    drawn = radius * magnification
    sheet.circle(ox + ax, oy + ay, drawn)
    for index, line in enumerate((detail.caption or "").split("\n")):
        if line:
            sheet.text(ox + ax, oy + ay - drawn - size * (1.6 + 1.3 * index),
                       line, size=size)
    for dim in detail.dims:
        if dim.kind != "aligned":
            raise ValueError("detail dimensions must be aligned")
        if not dim.label:
            raise ValueError("detail dimensions need a label: the geometry is "
                             "magnified and the number would be magnified too")
        _draw_dim(
            sheet,
            Dim("aligned", magnify(dim.a), magnify(dim.b),
                dim.offset * magnification, dim.label),
            2 * drawn, 2 * drawn, ox, oy,
            text_scale=size / TEXT_SIZE,
        )


def _draw_compass(sheet: SvgSheet, label: str, top: float, text_scale: float = 1.0):
    """Draw an up-pointing north arrow clear of everything already on the sheet.

    Placed past the right edge of the drawn view and its dimensions, level with
    the top of the view: a compass buried in the dimension lines is a compass
    nobody reads.
    """
    _, _, right, _ = sheet._bbox()
    x = right + COMPASS_GAP
    size = TEXT_SIZE * text_scale
    sheet.line(x, top - COMPASS_LEN, x, top, "leader")
    sheet.arrow(x, top, math.pi / 2)
    sheet.text(x, top + size * 0.7, label, size=size)


def render_part_drawing(
    name: str,
    shape,
    views: list[ViewSpec],
    qty: int,
    path,
    notes: list[str] | tuple[str, ...] | None = None,
    text_scale: float = 1.0,
):
    """One SVG sheet per part: views laid out left to right, dims, title.

    ``text_scale`` multiplies the caption, title and note sizes.  A sheet that
    gets scaled right down to fit a card needs its text sized as a fraction of
    the member, not in absolute millimetres, or nothing on it can be read.
    """
    if not math.isfinite(text_scale) or text_scale <= 0:
        raise ValueError("text_scale must be positive")
    for vs in views:
        if not math.isfinite(vs.presentation_scale) or vs.presentation_scale <= 0:
            raise ValueError("presentation_scale must be positive")
        if not math.isfinite(vs.dimension_text_scale) or vs.dimension_text_scale <= 0:
            raise ValueError("dimension_text_scale must be positive")
        if (
            vs.dimension_offset_scale is not None
            and (
                not math.isfinite(vs.dimension_offset_scale)
                or vs.dimension_offset_scale <= 0
            )
        ):
            raise ValueError("dimension_offset_scale must be positive")
        if (
            vs.vertical_dimension_offset_scale is not None
            and (
                not math.isfinite(vs.vertical_dimension_offset_scale)
                or vs.vertical_dimension_offset_scale <= 0
            )
        ):
            raise ValueError("vertical_dimension_offset_scale must be positive")
    sheet = SvgSheet()
    x_cursor = 0.0
    max_top = 0.0
    for vs in views:
        view_shape = shape if vs.shape is None else vs.shape
        vis, hid = project_edges(view_shape, vs.direction)
        vis = _scale_polys(vis, vs.presentation_scale)
        hid = _scale_polys(hid, vs.presentation_scale)
        offset_scale = (
            vs.presentation_scale
            if vs.dimension_offset_scale is None
            else vs.dimension_offset_scale
        )
        vertical_offset_scale = (
            offset_scale
            if vs.vertical_dimension_offset_scale is None
            else vs.vertical_dimension_offset_scale
        )
        dims = [
            _scale_dim(
                d, vs.presentation_scale, offset_scale, vertical_offset_scale
            )
            for d in vs.dims
        ]
        _, _, vw, vh = _bounds(vis + hid)
        left_room = max([14.0 - d.offset for d in dims if d.kind == "v" and d.offset < 0] + [0])
        ox, oy = x_cursor + left_room, 0.0
        sheet.add_polys(_shift(vis, ox, oy), "visible")
        if vs.show_hidden:
            sheet.add_polys(_shift(hid, ox, oy), "hidden")
        for d in dims:
            _draw_dim(
                sheet, d, vw, vh, ox, oy, text_scale=vs.dimension_text_scale
            )
        if vs.compass:
            _draw_compass(
                sheet, vs.compass, oy + vh, text_scale=vs.dimension_text_scale
            )
        for (lx, ly), label in vs.labels:
            sheet.text(
                ox + lx * vs.presentation_scale,
                oy + ly * vs.presentation_scale,
                label,
                size=TEXT_SIZE * vs.dimension_text_scale,
                anchor="start",
            )
        annotation_size = TEXT_SIZE * vs.dimension_text_scale
        for callout in vs.callouts:
            _draw_callout(sheet, callout, ox, oy, vs.presentation_scale,
                          annotation_size)
        for detail in vs.details:
            _draw_detail(sheet, detail, vis, hid, ox, oy,
                         vs.presentation_scale, annotation_size, vs.show_hidden)
        # Callouts and details are placed outside the dimension chains, so the
        # caption and the title have to clear them too — otherwise a label
        # above the view and the sheet title land on the same line.
        # A callout runs downward from `at`, so its bottom row — not its
        # anchor — is what the caption has to clear. Measured off the anchor, a
        # three-row label under a view lands on the caption's own line.
        annotated = [
            c.at[1] * vs.presentation_scale
            - row * _CALLOUT_LINE_STEP * annotation_size
            for c in vs.callouts
            for row in (0, c.text.count("\n"))
        ]
        annotated += [
            (d.at[1] + sign * d.radius * d.scale) * vs.presentation_scale
            for d in vs.details for sign in (-1, 1)
        ]
        below = min([d.offset for d in dims if d.kind == "h"] + annotated + [0])
        sheet.text(
            ox + vw / 2,
            below - 9 * text_scale,
            vs.caption or vs.direction,
            size=4 * text_scale,
        )
        right_room = max([d.offset - vw for d in dims if d.kind == "v" and d.offset > vw] + [0])
        # The gap between views has to grow with the text, or scaled-up labels
        # from one view print over the next one.
        x_cursor = ox + vw + right_room + 30 * text_scale
        max_top = max(
            [max_top, vh + max([d.offset - vh for d in dims if d.kind == "h"] + [0])]
            + annotated
        )
    sheet.text(
        (x_cursor - 30) / 2,
        max_top + 12 * text_scale,
        f"{name}  ×{qty}",
        size=5.5 * text_scale,
    )
    if notes:
        x0, y0, _, _ = sheet._bbox()
        note_size = TEXT_SIZE * text_scale
        line_gap = 2.0 * text_scale
        first_baseline = y0 - 5.0 * text_scale - note_size * 0.8
        line_step = note_size * 1.2 + line_gap
        for index, note in enumerate(notes):
            sheet.text(x0, first_baseline - index * line_step, note,
                       size=note_size, anchor="start")
    sheet.render(path)


#: The twelve edges of a bounding box, as pairs of (min/max) corner selectors
#: for x, y, z. Used to anchor leaders on a part's projected wireframe.
_BOX_EDGES = tuple(
    (a, b)
    for a, b in (
        ((i, j, 0), (i, j, 1)) for i in (0, 1) for j in (0, 1)
    )
) + tuple(
    (a, b)
    for a, b in (
        ((i, 0, k), (i, 1, k)) for i in (0, 1) for k in (0, 1)
    )
) + tuple(
    (a, b)
    for a, b in (
        ((0, j, k), (1, j, k)) for j in (0, 1) for k in (0, 1)
    )
)


def _nearest_on_segment(a, b, point):
    (ax, ay), (bx, by), (px, py) = a, b, point
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return a
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return (ax + t * dx, ay + t * dy)


def _leader_anchor(edges, label_point):
    """Where a leader should touch its part: the nearest point on its wireframe.

    Not the part's centre. A tall thin vertical projects its centre into the
    middle of the assembly, behind whatever else is there, so the leader looks
    like it points at some other part. The nearest point on the projected
    wireframe is on the part by construction, gives the shortest possible
    leader, and so keeps leaders from crossing each other.
    """
    best = None
    for a, b in edges:
        candidate = _nearest_on_segment(a, b, label_point)
        distance = math.hypot(candidate[0] - label_point[0],
                              candidate[1] - label_point[1])
        if best is None or distance < best[0]:
            best = (distance, candidate)
    return best[1]


def _convex_hull(points):
    """Andrew's monotone chain; a part's projected bbox corners → its outline."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_cross(p1, p2, q1, q2):
    """Closed-segment intersection; touching counts."""
    d1, d2 = _orient(q1, q2, p1), _orient(q1, q2, p2)
    d3, d4 = _orient(p1, p2, q1), _orient(p1, p2, q2)
    if d1 * d2 > 0 or d3 * d4 > 0:
        return False
    if d1 == d2 == d3 == d4 == 0:  # collinear: overlap iff bboxes overlap
        return (
            min(p1[0], p2[0]) <= max(q1[0], q2[0])
            and min(q1[0], q2[0]) <= max(p1[0], p2[0])
            and min(p1[1], p2[1]) <= max(q1[1], q2[1])
            and min(q1[1], q2[1]) <= max(p1[1], p2[1])
        )
    return True


def _point_in_polygon(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def _poly_edges(poly):
    return [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]


def _rect_corners(rect):
    left, bottom, right, top = rect
    return [(left, bottom), (right, bottom), (right, top), (left, top)]


def _inflate(rect, by):
    left, bottom, right, top = rect
    return (left - by, bottom - by, right + by, top + by)


def _rects_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _point_in_rect(pt, rect):
    return rect[0] <= pt[0] <= rect[2] and rect[1] <= pt[1] <= rect[3]


def _rect_intersects_polygon(rect, poly, poly_bbox):
    if not _rects_overlap(rect, poly_bbox):
        return False
    if any(_point_in_rect(p, rect) for p in poly):
        return True
    if any(_point_in_polygon(c, poly) for c in _rect_corners(rect)):
        return True
    return any(
        _segments_cross(a, b, c, d)
        for a, b in _poly_edges(_rect_corners(rect))
        for c, d in _poly_edges(poly)
    )


def _segment_intersects_rect(a, b, rect):
    if _point_in_rect(a, rect) or _point_in_rect(b, rect):
        return True
    return any(
        _segments_cross(a, b, c, d) for c, d in _poly_edges(_rect_corners(rect))
    )


def _segment_crosses_polygon(a, b, poly, poly_bbox):
    seg_box = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
    if not _rects_overlap(_inflate(seg_box, 1e-9), poly_bbox):
        return False
    if _point_in_polygon(a, poly) or _point_in_polygon(b, poly):
        return True
    return any(_segments_cross(a, b, c, d) for c, d in _poly_edges(poly))


def _bbox_of(points):
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def _label_extent(lines, size):
    """(width, height) of a label's text block, on the sheet's own metrics."""
    width = EXPLODED_CHAR_W * size * max(len(line) for line in lines)
    height = (1.2 + 1.3 * (len(lines) - 1)) * size
    return width, height


def _near_label_layout(labelled, part_corners, part_edges, drawn, size, groups):
    """Place each label in free space next to its part, clustered by group.

    Candidate slots lie on a half-pitch lattice over the drawing and
    EXPLODED_NEAR_REACH label pitches beyond it. Labels are placed most
    constrained first — fewest usable slots among their nearest — so a part
    boxed in by the assembly is labelled before a free-standing one takes
    its slot. A slot is out if its rectangle (plus clearance)
    touches any part's projected outline, an earlier label, or an earlier
    leader, or if its own leader would run through an earlier label. What is
    left is scored in label sizes: the leader's length, a penalty for every
    other part and every earlier leader it crosses, and a bonus for sitting
    next to — and lined up with — an already-placed label of the same group.
    That bonus is what turns "near its part" into "one component's labels
    together", and it is worth about six sizes of leader.

    Returns [(pname, lines, rect, side, leader_start, leader_end)], where
    `side` is the rectangle edge the leader leaves from.
    """
    gap = size
    hulls = {
        pname: _convex_hull(list(corners.values()))
        for pname, corners in part_corners.items()
    }
    hull_boxes = {pname: _bbox_of(hull) for pname, hull in hulls.items()}
    extents = {pname: _label_extent(lines, size) for pname, lines in labelled}
    slot_w = max(w for w, _ in extents.values())
    slot_h = max(h for _, h in extents.values())

    hx0, hy0, hx1, hy1 = _bbox_of([c for b in hull_boxes.values()
                                   for c in _rect_corners(b)])
    x0, y0 = min(drawn[0], hx0), min(drawn[1], hy0)
    x1, y1 = max(drawn[2], hx1), max(drawn[3], hy1)
    pitch_x, pitch_y = (slot_w + gap) / 2, (slot_h + gap) / 2
    slots = []
    left = x0 - EXPLODED_NEAR_REACH * (slot_w + gap)
    while left <= x1 + EXPLODED_NEAR_REACH * (slot_w + gap) - slot_w:
        bottom = y0 - EXPLODED_NEAR_REACH * (slot_h + gap)
        while bottom <= y1 + EXPLODED_NEAR_REACH * (slot_h + gap) - slot_h:
            rect = (left, bottom, left + slot_w, bottom + slot_h)
            padded = _inflate(rect, gap / 2)
            if not any(
                _rect_intersects_polygon(padded, hulls[p], hull_boxes[p])
                for p in hulls
            ):
                slots.append(rect)
            bottom += pitch_y
        left += pitch_x

    def leader_for(pname, rect):
        """Start on the rect edge facing the part, end on the part's wireframe."""
        left, bottom, right, top = rect
        cx, cy = (left + right) / 2, (bottom + top) / 2
        probe = _leader_anchor(part_edges[pname], (cx, cy))
        _, height = extents[pname]
        name_y = top - (slot_h - height) / 2 - 0.9 * size + 0.35 * size
        if probe[0] < left:
            side, start = "left", (left, name_y)
        elif probe[0] > right:
            side, start = "right", (right, name_y)
        elif probe[1] > top:
            side, start = "top", (cx, top)
        else:
            side, start = "bottom", (cx, bottom)
        return rect, side, start, _leader_anchor(part_edges[pname], start)

    # Every label's slots, nearest leader first.
    pools = {}
    for pname, _ in labelled:
        pool = [leader_for(pname, rect) for rect in slots]
        pool.sort(key=lambda c: (math.dist(c[2], c[3]), c[0]))
        pools[pname] = pool

    placement = {}  # pname -> (rect, side, start, end)

    def usable(candidate, others):
        """Hard rules against the labels in `others`: rects keep a gap (the
        lattice pitch leaves exactly one), a leader only has to miss the text
        itself, by a quarter gap."""
        rect, _, start, end = candidate
        near = _inflate(rect, 0.99 * gap)
        clear = _inflate(rect, gap / 4)
        for other_rect, _, a, b in others.values():
            if _rects_overlap(near, other_rect):
                return False
            if _segment_intersects_rect(a, b, clear):
                return False
            if _segment_intersects_rect(start, end, _inflate(other_rect, gap / 4)):
                return False
        return True

    def cost(pname, candidate, others):
        """Soft score in label sizes; lower is better."""
        rect, _, start, end = candidate
        score = math.dist(start, end) / size
        near = [o[0] for p, o in others.items() if groups[p] == groups[pname]]
        if any(_rects_overlap(_inflate(rect, 0.6 * gap), _inflate(o, 0.6 * gap))
               for o in near):
            score -= EXPLODED_NEAR_COHESION
        if any(abs(rect[0] - o[0]) < 1e-6 or abs(rect[1] - o[1]) < 1e-6
               for o in near):
            score -= EXPLODED_NEAR_ALIGN
        score += EXPLODED_NEAR_CROSS_PART * sum(
            _segment_crosses_polygon(start, end, hulls[p], hull_boxes[p])
            for p in hulls if p != pname
        )
        score += EXPLODED_NEAR_CROSS_LEADER * sum(
            _segments_cross(start, end, a, b) for _, _, a, b in others.values()
        )
        return score

    def best_slot(pname, others):
        """(cost, candidate) of the cheapest of the nearest usable slots."""
        found = []
        for candidate in pools[pname]:
            if usable(candidate, others):
                found.append((cost(pname, candidate, others), candidate))
                if len(found) == EXPLODED_NEAR_CANDIDATES:
                    break
        if not found:
            raise ValueError(f"no free space to label {pname!r}")
        return min(found, key=lambda f: (f[0], f[1][0]))

    # Greedy, most constrained first: at each step the label with the fewest
    # usable slots among its nearest is placed, so a part boxed in by the
    # assembly gets its one good slot before a free-standing part takes it.
    remaining = [pname for pname, _ in labelled]
    while remaining:
        pname = min(
            remaining,
            key=lambda p: (
                sum(usable(c, placement) for c in pools[p][:EXPLODED_NEAR_POOL]),
                remaining.index(p),
            ),
        )
        remaining.remove(pname)
        placement[pname] = best_slot(pname, placement)[1]

    # Then improve: greedy order still strands the odd label far from its
    # part once its neighbourhood is full. Take the labels worst first and
    # move each to a better slot, or swap it with another label when both
    # come out ahead, until nothing improves.
    def without(*names):
        return {p: c for p, c in placement.items() if p not in names}

    for _ in range(EXPLODED_NEAR_PASSES):
        improved = False
        worst_first = sorted(
            placement, key=lambda p: -cost(p, placement[p], without(p))
        )
        for pname in worst_first:
            others = without(pname)
            current = cost(pname, placement[pname], others)
            gain, action = EXPLODED_NEAR_MIN_GAIN, None
            moved_cost, moved = best_slot(pname, others)
            if current - moved_cost > gain:
                gain, action = current - moved_cost, {pname: moved}
            for other in placement:
                if other == pname:
                    continue
                rest = without(pname, other)
                mine = leader_for(pname, placement[other][0])
                theirs = leader_for(other, placement[pname][0])
                if not (usable(mine, rest | {other: theirs})
                        and usable(theirs, rest | {pname: mine})):
                    continue
                before = current + cost(other, placement[other], without(other))
                after = (cost(pname, mine, rest | {other: theirs})
                         + cost(other, theirs, rest | {pname: mine}))
                if before - after > gain:
                    gain, action = before - after, {pname: mine, other: theirs}
            if action:
                placement.update(action)
                improved = True
        if not improved:
            break

    return [
        (pname, lines, *placement[pname]) for pname, lines in labelled
    ]


def render_exploded(
    placed: dict,
    explode: float,
    path,
    view: str = "iso",
    labels: dict[str, str] | None = None,
    title: str = "exploded view",
    layout: str = "columns",
    groups: dict[str, str] | None = None,
):
    """Exploded assembly view with part labels.

    placed: {name: solid} in assembled positions. Each part is translated
    away from the assembly center by explode * (its center - assembly center).

    A label of None (or "") draws the part but gives it no text and no leader.
    Use it for repeats: a dozen identical parts stacked in one view means a
    dozen leaders into the same stack, and the drawing stops being readable.
    Every placed key must still appear in `labels`, so a typo is still an error
    rather than a silently missing label.

    layout "columns" balances the labels into one column either side of the
    drawing. layout "near" puts each label in free space next to its part
    instead, and `groups` — {part name: group name} — clusters the labels of
    one sub-assembly together; a part left out of `groups` is a group of its
    own. Use "near" when a long assembly leaves empty paper around its parts
    that two edge columns cannot reach; see `_near_label_layout`.
    """
    from build123d import Pos

    if not placed:
        raise ValueError("placed must contain at least one part")
    if labels is not None and set(labels) != set(placed):
        raise ValueError("labels must match placed keys exactly")
    if layout not in ("columns", "near"):
        raise ValueError(f"layout must be 'columns' or 'near', not {layout!r}")
    if groups is not None and set(groups) - set(placed):
        raise ValueError(
            f"groups names parts that are not placed: "
            f"{sorted(set(groups) - set(placed))}"
        )
    label_groups = {pname: pname for pname in placed} | (groups or {})
    display_labels = (
        {pname: pname for pname in placed} if labels is None else labels
    )
    if not any(display_labels.values()):
        raise ValueError("at least one part must carry a label")

    bounds = [solid.bounding_box() for solid in placed.values()]
    center = Vector(
        (min(bb.min.X for bb in bounds) + max(bb.max.X for bb in bounds)) / 2,
        (min(bb.min.Y for bb in bounds) + max(bb.max.Y for bb in bounds)) / 2,
        (min(bb.min.Z for bb in bounds) + max(bb.max.Z for bb in bounds)) / 2,
    )
    exploded = {}
    for pname, solid in placed.items():
        off = (solid.bounding_box().center() - center) * explode
        exploded[pname] = Pos(off.X, off.Y, off.Z) * solid

    compound = Compound(children=list(exploded.values()))
    vis, hid = project_edges(compound, view)

    # Map 3D label anchors into the normalized 2D frame: orthographic basis,
    # then align bbox mins (HLR output is self-centered, scale is 1:1).
    to2d = view_map(exploded.values(), view)

    part_corners = {}
    for pname, solid in exploded.items():
        bb = solid.bounding_box()
        axis = ((bb.min.X, bb.max.X), (bb.min.Y, bb.max.Y), (bb.min.Z, bb.max.Z))
        part_corners[pname] = {
            (i, j, k): to2d((axis[0][i], axis[1][j], axis[2][k]))
            for i in (0, 1)
            for j in (0, 1)
            for k in (0, 1)
        }
    part_edges = {
        pname: [(pts[a], pts[b]) for a, b in _BOX_EDGES]
        for pname, pts in part_corners.items()
    }

    sheet = SvgSheet()
    sheet.add_polys(vis, "visible")
    x0, y0, x1, y1 = _bounds(vis + hid)
    w, h = x1 - x0, y1 - y0
    label_size = max(
        EXPLODED_LABEL_MIN,
        min(EXPLODED_LABEL_MAX, 4 * max(w, h) / EXPLODED_LABEL_SCALE),
    )

    label_positions = []
    for pname, solid in exploded.items():
        if not display_labels[pname]:
            continue
        cx, cy = to2d(solid.bounding_box().center())
        label_positions.append((pname, cx, cy))

    if layout == "near":
        # Group order is first appearance; within a group, top down and left
        # to right, so the first label of a cluster is the one the rest stack
        # under.
        order = {}
        for pname, _, _ in label_positions:
            order.setdefault(label_groups[pname], len(order))
        label_positions.sort(
            key=lambda label: (order[label_groups[label[0]]], -label[2], label[1])
        )
        labelled = [
            (pname, display_labels[pname].split("\n"))
            for pname, _, _ in label_positions
        ]
        arrow_scale = label_size / (TEXT_SIZE * 2)
        highest_label = y1
        for pname, lines, rect, side, start, end in _near_label_layout(
            labelled, part_corners, part_edges, (x0, y0, x1, y1), label_size,
            label_groups,
        ):
            sheet.line(start[0], start[1], end[0], end[1], style="leader")
            sheet.arrow(end[0], end[1],
                        math.atan2(end[1] - start[1], end[0] - start[0]),
                        scale=arrow_scale)
            left, bottom, right, top = rect
            _, height = _label_extent(lines, label_size)
            first_baseline = top - ((top - bottom) - height) / 2 - 0.9 * label_size
            text_x, anchor = {
                "left": (left, "start"),
                "right": (right, "end"),
                "top": ((left + right) / 2, "middle"),
                "bottom": ((left + right) / 2, "middle"),
            }[side]
            for line_index, line in enumerate(lines):
                sheet.text(text_x, first_baseline - line_index * label_size * 1.3,
                           line, size=label_size, anchor=anchor)
            highest_label = max(highest_label, top)
        title_size = label_size * 1.3
        sheet.text((x0 + x1) / 2, highest_label + 2 * title_size, title,
                   size=title_size)
        sheet.render(path)
        return

    # Keep labels outside the assembly and balance them into two columns.
    # Sorting by projected x preserves locality; sorting each column by y keeps
    # leader crossings predictable. Text bounds are 1.2 * size high, so this
    # pitch leaves a further 1.5 * size of clear space between rows.
    label_positions.sort(key=lambda label: (label[1], label[2], label[0]))
    split = (len(label_positions) + 1) // 2
    columns = (
        (label_positions[:split], x0 - EXPLODED_COLUMN_GAP, "end"),
        (label_positions[split:], x1 + EXPLODED_COLUMN_GAP, "start"),
    )
    # A label is a name line plus a cut-dimension line, each 1.2 sizes
    # tall on a 1.3 pitch, so a row needs 2.5 sizes before its gap.
    row_pitch = label_size * (2.5 + EXPLODED_ROW_GAP)
    highest_label = y1
    for column, label_x, anchor in columns:
        column.sort(key=lambda label: (-label[2], label[0]))
        first_y = (y0 + y1) / 2 + (len(column) - 1) * row_pitch / 2
        for index, (pname, _, _) in enumerate(column):
            label_y = first_y - index * row_pitch
            anchor_x, anchor_y = _leader_anchor(
                part_edges[pname], (label_x, label_y)
            )
            sheet.line(anchor_x, anchor_y, label_x, label_y, style="leader")
            # An arrowhead at the part end. In an exploded view of anything tall
            # and narrow the interior parts sit behind the outer ones, so a
            # leader has to cross something to reach them; without a head you
            # cannot tell which part it stops at.
            sheet.arrow(
                anchor_x,
                anchor_y,
                math.atan2(anchor_y - label_y, anchor_x - label_x),
                scale=label_size / (TEXT_SIZE * 2),
            )
            for line_index, line in enumerate(display_labels[pname].split("\n")):
                sheet.text(
                    label_x,
                    label_y - line_index * label_size * 1.3,
                    line,
                    size=label_size,
                    anchor=anchor,
                )
            highest_label = max(highest_label, label_y + label_size * 0.8)

    title_size = label_size * 1.3
    title_y = highest_label + 2 * title_size
    sheet.text((x0 + x1) / 2, title_y, title, size=title_size)
    sheet.render(path)
