import builtins
import math
from itertools import combinations
from xml.etree import ElementTree

import pytest
from build123d import Vector

from cadkit.draw import TEXT_SIZE, Dim, ViewSpec, drawing, render_part_drawing
from cadkit.wood import block

SVG_NS = {"svg": "http://www.w3.org/2000/svg"}
OMITTED = object()


def _render_part(path, notes=OMITTED):
    kwargs = {} if notes is OMITTED else {"notes": notes}
    render_part_drawing(
        "panel",
        block(100, 20, 50),
        [ViewSpec("front")],
        1,
        path,
        **kwargs,
    )
    return path.read_text()


def _text_bounds(node):
    """Match SvgSheet's conservative text bounds in rendered coordinates."""
    x = float(node.attrib["x"])
    y = float(node.attrib["y"])
    size = float(node.attrib["font-size"])
    width = 0.62 * size * len(node.text or "")
    anchor = node.attrib["text-anchor"]
    x_min = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
    return x_min, y - size * 0.8, x_min + width, y + size * 0.4


def _rectangles_are_disjoint(first, second):
    return (
        first[2] <= second[0]
        or second[2] <= first[0]
        or first[3] <= second[1]
        or second[3] <= first[1]
    )


def test_part_drawing_renders_ordered_notes_below_existing_content(tmp_path):
    note_texts = ["Leave the front edge proud.", "Ease after final assembly."]
    svg = _render_part(tmp_path / "notes.svg", notes=note_texts)
    root = ElementTree.fromstring(svg)
    texts = root.findall("svg:text", SVG_NS)
    notes = texts[-2:]

    assert [element.text for element in notes] == note_texts
    assert [element.get("text-anchor") for element in notes] == ["start", "start"]

    xs = [float(element.get("x")) for element in notes]
    assert xs[0] == xs[1]
    assert xs[0] >= 10.0

    ys = [float(element.get("y")) for element in notes]
    assert ys == sorted(set(ys))

    _, _, _, viewbox_height = map(float, root.get("viewBox").split())
    final_text_bottom = ys[-1] + TEXT_SIZE * 0.4
    assert viewbox_height - final_text_bottom == pytest.approx(10.0, abs=0.01)


def test_part_drawing_empty_notes_are_exact_no_ops(tmp_path):
    omitted = _render_part(tmp_path / "omitted.svg")
    explicit_none = _render_part(tmp_path / "none.svg", notes=None)
    empty_tuple = _render_part(tmp_path / "empty.svg", notes=())

    assert omitted == explicit_none == empty_tuple


def test_part_drawing_preserves_xml_special_characters_in_text(tmp_path):
    title = "A & B < C > D"
    note = "Keep 5 < gap & 7 > clearance"
    output = tmp_path / "escaped.svg"

    render_part_drawing(
        title,
        block(100, 20, 50),
        [ViewSpec("front")],
        1,
        output,
        notes=(note,),
    )

    root = ElementTree.parse(output).getroot()
    rendered_text = [
        node.text for node in root.findall("svg:text", SVG_NS)
    ]
    assert f"{title}  ×1" in rendered_text
    assert note in rendered_text


def test_svg_sheet_render_writes_utf8_and_roundtrips_unicode(
    tmp_path, monkeypatch
):
    text = "äöåÄÖÅ Ø × ° –"
    output = tmp_path / "unicode.svg"
    encodings = []

    def recording_open(path, mode, encoding=None):
        encodings.append(encoding)
        return builtins.open(path, mode, encoding=encoding)

    monkeypatch.setattr(drawing, "open", recording_open, raising=False)
    sheet = drawing.SvgSheet()
    sheet.text(0, 0, text)
    sheet.render(output)

    assert encodings == ["utf-8"]
    root = ElementTree.fromstring(output.read_text(encoding="utf-8"))
    assert root.find("svg:text", SVG_NS).text == text


def test_view_spec_shape_is_appended_for_positional_compatibility():
    legacy = ViewSpec("front", [], False, "legacy caption")

    assert legacy.direction == "front"
    assert legacy.dims == []
    assert legacy.show_hidden is False
    assert legacy.caption == "legacy caption"
    assert legacy.shape is None


def test_part_drawing_scales_view_geometry_but_not_dimension_text(tmp_path):
    shape = block(100, 20, 50)
    dims = [Dim("h", 0, 100, -10), Dim("v", 0, 50, -10)]

    def render(scale, name):
        output = tmp_path / name
        render_part_drawing(
            "panel",
            shape,
            [ViewSpec("front", dims=dims, presentation_scale=scale)],
            1,
            output,
        )
        return ElementTree.parse(output).getroot()

    def longest_horizontal_line(root, stroke):
        lines = []
        for node in root.findall("svg:polyline", SVG_NS):
            if node.get("stroke") != stroke:
                continue
            points = [
                tuple(map(float, point.split(",")))
                for point in node.attrib["points"].split()
            ]
            if len(points) == 2 and points[0][1] == pytest.approx(points[1][1]):
                lines.append(points)
        return max(lines, key=lambda line: abs(line[1][0] - line[0][0]))

    unscaled = render(1.0, "unscaled.svg")
    scaled = render(0.1, "scaled.svg")

    dimension_text = {
        node.text: float(node.attrib["font-size"])
        for node in scaled.findall("svg:text", SVG_NS)
    }
    assert dimension_text["100"] == TEXT_SIZE
    assert dimension_text["50"] == TEXT_SIZE

    for stroke in ("#111", "#555"):
        unscaled_line = longest_horizontal_line(unscaled, stroke)
        scaled_line = longest_horizontal_line(scaled, stroke)
        unscaled_distance = abs(unscaled_line[1][0] - unscaled_line[0][0])
        scaled_distance = abs(scaled_line[1][0] - scaled_line[0][0])
        assert scaled_distance == pytest.approx(unscaled_distance / 10)

    for invalid_scale in (0, -1, float("nan"), float("inf"), -float("inf")):
        with pytest.raises(
            ValueError, match="^presentation_scale must be positive$"
        ):
            render(invalid_scale, f"invalid-{invalid_scale}.svg")


def test_part_drawing_default_presentation_scale_is_unchanged(tmp_path):
    shape = block(100, 20, 50)
    dims = [Dim("h", 0, 100, -10)]
    default_output = tmp_path / "default.svg"
    explicit_output = tmp_path / "explicit.svg"
    offset_default_output = tmp_path / "offset-default.svg"

    render_part_drawing(
        "panel", shape, [ViewSpec("front", dims=dims)], 1, default_output
    )
    render_part_drawing(
        "panel",
        shape,
        [ViewSpec("front", dims=dims, presentation_scale=1.0)],
        1,
        explicit_output,
    )
    render_part_drawing(
        "panel",
        shape,
        [
            ViewSpec(
                "front",
                dims=dims,
                presentation_scale=1.0,
                dimension_offset_scale=None,
                vertical_dimension_offset_scale=None,
                dimension_text_scale=1.0,
            )
        ],
        1,
        offset_default_output,
    )

    assert default_output.read_text() == explicit_output.read_text()
    assert default_output.read_text() == offset_default_output.read_text()


def test_part_drawing_scales_dimension_offsets_independently(tmp_path):
    output = tmp_path / "offset-scale.svg"
    render_part_drawing(
        "panel",
        block(100, 20, 50),
        [
            ViewSpec(
                "front",
                [Dim("h", 0, 100, -10), Dim("v", 0, 50, -10)],
                presentation_scale=0.1,
                dimension_offset_scale=0.2,
                vertical_dimension_offset_scale=0.3,
            )
        ],
        1,
        output,
    )
    root = ElementTree.parse(output).getroot()

    def two_point_lines(stroke):
        return [
            [tuple(map(float, point.split(","))) for point in node.attrib["points"].split()]
            for node in root.findall("svg:polyline", SVG_NS)
            if node.get("stroke") == stroke and len(node.attrib["points"].split()) == 2
        ]

    visible = two_point_lines("#111")
    dimensions = two_point_lines("#555")
    visible_bottom = max(
        line[0][1]
        for line in visible
        if line[0][1] == pytest.approx(line[1][1])
    )
    visible_left = min(
        line[0][0]
        for line in visible
        if line[0][0] == pytest.approx(line[1][0])
    )
    horizontal_dimension = max(
        (line for line in dimensions if line[0][1] == pytest.approx(line[1][1])),
        key=lambda line: abs(line[1][0] - line[0][0]),
    )
    vertical_dimension = max(
        (line for line in dimensions if line[0][0] == pytest.approx(line[1][0])),
        key=lambda line: abs(line[1][1] - line[0][1]),
    )

    assert abs(horizontal_dimension[1][0] - horizontal_dimension[0][0]) == pytest.approx(10)
    assert abs(vertical_dimension[1][1] - vertical_dimension[0][1]) == pytest.approx(5)
    assert horizontal_dimension[0][1] - visible_bottom == pytest.approx(2)
    assert visible_left - vertical_dimension[0][0] == pytest.approx(3)

    for invalid_scale in (0, -1, float("nan"), float("inf"), -float("inf")):
        with pytest.raises(
            ValueError, match="^dimension_offset_scale must be positive$"
        ):
            render_part_drawing(
                "panel",
                block(100, 20, 50),
                [ViewSpec("front", dimension_offset_scale=invalid_scale)],
                1,
                tmp_path / f"invalid-offset-{invalid_scale}.svg",
            )
        with pytest.raises(
            ValueError,
            match="^vertical_dimension_offset_scale must be positive$",
        ):
            render_part_drawing(
                "panel",
                block(100, 20, 50),
                [
                    ViewSpec(
                        "front",
                        vertical_dimension_offset_scale=invalid_scale,
                    )
                ],
                1,
                tmp_path / f"invalid-vertical-offset-{invalid_scale}.svg",
            )
        with pytest.raises(
            ValueError, match="^dimension_text_scale must be positive$"
        ):
            render_part_drawing(
                "panel",
                block(100, 20, 50),
                [ViewSpec("front", dimension_text_scale=invalid_scale)],
                1,
                tmp_path / f"invalid-text-scale-{invalid_scale}.svg",
            )


def test_part_drawing_projects_each_view_override_as_one_shape(
    tmp_path, monkeypatch
):
    default_shape = block(100, 20, 50)
    detail_shape = block(30, 10, 70)
    projected = []

    def record_projection(shape, view):
        projected.append((shape, view))
        return ([[(0, 0), (10, 0), (10, 10), (0, 10)]], [])

    monkeypatch.setattr(drawing, "project_edges", record_projection)
    render_part_drawing(
        "panel",
        default_shape,
        [
            ViewSpec("front", shape=detail_shape),
            ViewSpec("right"),
        ],
        1,
        tmp_path / "per-view-shape.svg",
    )

    assert projected == [(detail_shape, "front"), (default_shape, "right")]


def test_aligned_dimension_anchors_extensions_arrows_and_measured_length():
    sheet = drawing.SvgSheet()
    dim = drawing.Dim("aligned", (10, 20), (70, 100), 10)

    drawing._draw_dim(sheet, dim, vw=120, vh=120, ox=5, oy=7)

    start = (15, 27)
    end = (75, 107)
    unit = (0.6, 0.8)
    normal = (-0.8, 0.6)
    dim_start = (
        start[0] + normal[0] * dim.offset,
        start[1] + normal[1] * dim.offset,
    )
    dim_end = (
        end[0] + normal[0] * dim.offset,
        end[1] + normal[1] * dim.offset,
    )

    assert sheet.polys[0][0][0] == pytest.approx(
        (start[0] + normal[0], start[1] + normal[1])
    )
    assert sheet.polys[1][0][0] == pytest.approx(
        (end[0] + normal[0], end[1] + normal[1])
    )
    assert sheet.polys[2][0][0] == pytest.approx(dim_start)
    assert sheet.polys[2][0][1] == pytest.approx(dim_end)
    assert sheet.arrows[0][:2] == pytest.approx(dim_start)
    assert sheet.arrows[1][:2] == pytest.approx(dim_end)
    assert sheet.arrows[0][2] == pytest.approx(
        math.atan2(unit[1], unit[0]) + math.pi
    )
    assert sheet.arrows[1][2] == pytest.approx(
        math.atan2(unit[1], unit[0])
    )
    assert sheet.texts[0][2] == "100"


def test_exploded_labels_are_preserved_separated_and_leader_associated(
    tmp_path, monkeypatch
):
    placed = {
        f"long_part_label_{index}": block(10, 10, 10)
        for index in range(6)
    }

    def fixed_projection(shape, view):
        return ([[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]], [])

    monkeypatch.setattr(drawing, "project_edges", fixed_projection)
    output = tmp_path / "exploded.svg"
    drawing.render_exploded(placed, explode=0.5, path=output)

    root = ElementTree.parse(output).getroot()
    labels = [
        node
        for node in root.findall("svg:text", SVG_NS)
        if node.text in placed
    ]
    assert len(labels) == len(placed)
    assert {node.text for node in labels} == set(placed)
    assert "exploded view" in [
        node.text for node in root.findall("svg:text", SVG_NS)
    ]
    assert all(
        drawing.EXPLODED_LABEL_MIN
        <= float(node.attrib["font-size"])
        <= drawing.EXPLODED_LABEL_MAX
        for node in labels
    )

    rectangles = [_text_bounds(node) for node in labels]
    assert all(
        _rectangles_are_disjoint(first, second)
        for first, second in combinations(rectangles, 2)
    )

    outline = next(
        node
        for node in root.findall("svg:polyline", SVG_NS)
        if node.attrib.get("stroke") == "#111"
    )
    geometry_x = [
        float(point.split(",")[0])
        for point in outline.attrib["points"].split()
    ]
    for label, bounds in zip(labels, rectangles):
        if label.attrib["text-anchor"] == "end":
            assert bounds[2] < min(geometry_x)
        else:
            assert bounds[0] > max(geometry_x)

    leaders = [
        node
        for node in root.findall("svg:polyline", SVG_NS)
        if node.attrib.get("stroke") == "#555"
    ]
    assert len(leaders) == len(placed)


def _label_rects(root, names):
    """Bounding rect of each part's label text block, in SVG coords."""
    rects = {}
    for node in root.findall("svg:text", SVG_NS):
        if node.text in names:
            rects[node.text] = _text_bounds(node)
    return rects


def test_exploded_near_layout_clusters_each_group_beside_its_parts(tmp_path):
    """Two stacks of boards far apart: with layout="near" each stack's labels
    sit on its own side of the sheet, clear of every part and of each other,
    and no leader runs through another label's text."""
    placed = {}
    for index in range(4):
        placed[f"left_board_{index}"] = block(300, 200, 18, at=(0, 0, index * 100))
        placed[f"right_board_{index}"] = block(300, 200, 18,
                                              at=(2000, 0, index * 100))
    groups = {name: name.split("_")[0] for name in placed}
    labels = {name: f"{name}\n300×200×18" for name in placed}
    output = tmp_path / "near.svg"
    drawing.render_exploded(placed, explode=0.3, path=output, view="front",
                            labels=labels, layout="near", groups=groups)

    root = ElementTree.parse(output).getroot()
    rects = _label_rects(root, set(placed))
    assert set(rects) == set(placed)
    assert all(
        _rectangles_are_disjoint(first, second)
        for first, second in combinations(rects.values(), 2)
    )

    # every label is nearer its own stack than the other one, and the two
    # groups do not interleave: all left labels are left of all right labels
    outline = [
        node for node in root.findall("svg:polyline", SVG_NS)
        if node.attrib.get("stroke") == "#111"
    ]
    xs = sorted(
        float(point.split(",")[0])
        for node in outline for point in node.attrib["points"].split()
    )
    left_stack_x, right_stack_x = xs[0], xs[-1]
    for name, (x0, _, x1, _) in rects.items():
        centre = (x0 + x1) / 2
        if name.startswith("left"):
            assert abs(centre - left_stack_x) < abs(centre - right_stack_x)
        else:
            assert abs(centre - right_stack_x) < abs(centre - left_stack_x)
    assert max(r[2] for n, r in rects.items() if n.startswith("left")) < min(
        r[0] for n, r in rects.items() if n.startswith("right")
    )

    # a leader per label, and none of them run through any label's text
    leaders = [
        [tuple(map(float, point.split(","))) for point in node.attrib["points"].split()]
        for node in root.findall("svg:polyline", SVG_NS)
        if node.attrib.get("stroke") == "#555"
    ]
    assert len(leaders) == len(placed)
    for a, b in leaders:
        for rect in rects.values():
            inner = (rect[0] + 0.5, rect[1] + 0.5, rect[2] - 0.5, rect[3] - 0.5)
            touches_own = (
                abs(a[0] - rect[0]) < 0.6 or abs(a[0] - rect[2]) < 0.6
                or abs(a[1] - rect[1]) < 0.6 or abs(a[1] - rect[3]) < 0.6
            )
            if not touches_own:
                assert not drawing._segment_intersects_rect(a, b, inner)


def test_exploded_near_layout_rejects_bad_arguments(tmp_path):
    placed = {"a": block(10, 10, 10), "b": block(10, 10, 10, at=(30, 0, 0))}
    with pytest.raises(ValueError, match="layout"):
        drawing.render_exploded(placed, explode=0.5, path=tmp_path / "x.svg",
                                layout="spiral")
    with pytest.raises(ValueError, match="not placed"):
        drawing.render_exploded(placed, explode=0.5, path=tmp_path / "x.svg",
                                layout="near", groups={"c": "g"})
    # a part left out of groups is a group of its own, not an error
    drawing.render_exploded(placed, explode=0.5, path=tmp_path / "ok.svg",
                            layout="near", groups={"a": "g"})
    assert (tmp_path / "ok.svg").read_text().startswith("<svg")


def test_exploded_near_layout_geometry_helpers():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert drawing._convex_hull([(0, 0), (10, 0), (5, 5), (10, 10), (0, 10)]) == [
        (0, 0), (10, 0), (10, 10), (0, 10)
    ]
    assert drawing._point_in_polygon((5, 5), square)
    assert not drawing._point_in_polygon((15, 5), square)
    assert drawing._segments_cross((0, 0), (10, 10), (0, 10), (10, 0))
    assert not drawing._segments_cross((0, 0), (1, 1), (2, 2), (3, 3))
    assert drawing._segments_cross((0, 0), (2, 2), (1, 1), (3, 3))  # collinear overlap
    box = (0, 0, 10, 10)
    assert drawing._rect_intersects_polygon((5, 5, 15, 15), square, box)
    assert drawing._rect_intersects_polygon((-5, -5, 15, 15), square, box)  # engulfs
    assert drawing._rect_intersects_polygon((2, 2, 4, 4), square, box)  # inside
    assert not drawing._rect_intersects_polygon((11, 11, 15, 15), square, box)
    assert drawing._segment_intersects_rect((-5, 5), (15, 5), (0, 0, 10, 10))
    assert not drawing._segment_intersects_rect((-5, 15), (15, 15), (0, 0, 10, 10))
    assert drawing._segment_crosses_polygon((-5, 5), (15, 5), square, box)
    assert not drawing._segment_crosses_polygon((-5, 15), (15, 15), square, box)


def test_exploded_render_uses_localized_labels_and_title(tmp_path, monkeypatch):
    placed = {
        "roof_frame": block(10, 12, 14),
        "front_post": block(8, 10, 16, at=(20, 0, 0)),
    }
    labels = {
        "roof_frame": "Katon runko",
        "front_post": "Etutolppa äöå",
    }
    title = "Katoksen räjäytyskuva"

    monkeypatch.setattr(
        drawing,
        "project_edges",
        lambda shape, view: (
            [[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]],
            [],
        ),
    )
    output = tmp_path / "localized-exploded.svg"
    drawing.render_exploded(
        placed, 0.2, output, labels=labels, title=title
    )

    root = ElementTree.fromstring(output.read_text(encoding="utf-8"))
    rendered_text = [node.text for node in root.findall("svg:text", SVG_NS)]
    assert set(labels.values()).issubset(rendered_text)
    assert title in rendered_text
    assert set(placed).isdisjoint(rendered_text)


@pytest.mark.parametrize(
    "labels",
    [
        {"first": "Ensimmäinen"},
        {
            "first": "Ensimmäinen",
            "second": "Toinen",
            "extra": "Ylimääräinen",
        },
    ],
)
def test_exploded_render_rejects_label_keys_that_do_not_match_placed(
    tmp_path, labels
):
    placed = {
        "first": block(10, 10, 10),
        "second": block(10, 10, 10, at=(20, 0, 0)),
    }

    with pytest.raises(
        ValueError, match="^labels must match placed keys exactly$"
    ):
        drawing.render_exploded(
            placed,
            0.2,
            tmp_path / "invalid-labels.svg",
            labels=labels,
        )


def test_exploded_render_preserves_input_shapes(tmp_path, monkeypatch):
    placed = {
        "first": block(10, 12, 14, at=(5, 10, 15)),
        "second": block(16, 18, 20, at=(40, 50, 60)),
    }
    original = {
        name: (
            solid,
            solid.parent,
            tuple(solid.location.position),
            tuple(solid.location.orientation),
        )
        for name, solid in placed.items()
    }

    monkeypatch.setattr(
        drawing,
        "project_edges",
        lambda shape, view: (
            [[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]],
            [],
        ),
    )
    drawing.render_exploded(placed, explode=0.5, path=tmp_path / "safe.svg")

    for name, (solid, parent, position, orientation) in original.items():
        assert placed[name] is solid
        assert solid.parent is parent
        assert tuple(solid.location.position) == position
        assert tuple(solid.location.orientation) == orientation


def test_exploded_render_rejects_empty_input(tmp_path):
    with pytest.raises(
        ValueError, match="^placed must contain at least one part$"
    ):
        drawing.render_exploded({}, explode=0.5, path=tmp_path / "empty.svg")


def test_exploded_leaders_connect_projected_anchors_to_matching_labels(
    tmp_path, monkeypatch
):
    explode = 0.5
    placed = {
        "lower_left": block(10, 12, 14, at=(5, 10, 15)),
        "upper_left": block(16, 18, 20, at=(25, 30, 45)),
        "lower_right": block(12, 14, 16, at=(55, 5, 10)),
        "upper_right": block(18, 20, 22, at=(75, 35, 50)),
    }
    boxes = {name: solid.bounding_box() for name, solid in placed.items()}

    monkeypatch.setattr(
        drawing,
        "project_edges",
        lambda shape, view: (
            [[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]],
            [],
        ),
    )
    output = tmp_path / "leaders.svg"
    drawing.render_exploded(
        placed, explode=explode, path=output, view="top"
    )

    center = Vector(
        (min(bb.min.X for bb in boxes.values())
         + max(bb.max.X for bb in boxes.values())) / 2,
        (min(bb.min.Y for bb in boxes.values())
         + max(bb.max.Y for bb in boxes.values())) / 2,
        (min(bb.min.Z for bb in boxes.values())
         + max(bb.max.Z for bb in boxes.values())) / 2,
    )
    right, up = drawing.view_basis("top")
    exploded_anchors = {}
    part_corners = {}
    for name, bb in boxes.items():
        offset = (bb.center() - center) * explode
        exploded_anchors[name] = bb.center() + offset
        part_corners[name] = {
            (i, j, k): (point.dot(right), point.dot(up))
            for i, x in enumerate((bb.min.X + offset.X, bb.max.X + offset.X))
            for j, y in enumerate((bb.min.Y + offset.Y, bb.max.Y + offset.Y))
            for k, z in enumerate((bb.min.Z + offset.Z, bb.max.Z + offset.Z))
            for point in [Vector(x, y, z)]
        }
    projected_corners = [
        point for pts in part_corners.values() for point in pts.values()
    ]
    projected_min_x = min(x for x, _ in projected_corners)
    projected_min_y = min(y for _, y in projected_corners)

    root = ElementTree.parse(output).getroot()
    children = list(root)
    outline_start = tuple(
        map(float, children[0].attrib["points"].split()[0].split(","))
    )
    leaders = [
        [
            tuple(map(float, point.split(",")))
            for point in node.attrib["points"].split()
        ]
        for node in children
        if node.tag.endswith("polyline")
        and node.attrib.get("stroke") == "#555"
    ]
    for label in children:
        if not label.tag.endswith("text") or label.text not in placed:
            continue
        label_position = (
            float(label.attrib["x"]),
            float(label.attrib["y"]),
        )
        matching_leaders = [
            points
            for points in leaders
            if points[1] == pytest.approx(label_position, abs=0.01)
        ]
        assert len(matching_leaders) == 1
        leader_points = matching_leaders[0]

        # The leader lands on the nearest point of the part's projected
        # wireframe, not on its centre: a tall thin part projects its centre
        # behind whatever else is in the way, and the leader then reads as
        # pointing at the wrong part.
        def to_svg(point):
            return (
                outline_start[0] + point[0] - projected_min_x,
                outline_start[1] - (point[1] - projected_min_y),
            )

        corners = part_corners[label.text]
        edges = [
            (to_svg(corners[a]), to_svg(corners[b]))
            for a, b in drawing._BOX_EDGES
        ]
        nearest = drawing._leader_anchor(edges, label_position)
        assert leader_points[0] == pytest.approx(nearest, abs=0.01)

        # ...and it really is on the wireframe, and really is the closest
        # point on it, which is what makes the shortest non-crossing leader.
        def distance(point):
            return math.hypot(point[0] - label_position[0],
                              point[1] - label_position[1])

        anchor_point = leader_points[0]
        on_wireframe = min(
            math.hypot(candidate[0] - anchor_point[0],
                       candidate[1] - anchor_point[1])
            for a, b in edges
            for candidate in [drawing._nearest_on_segment(a, b, anchor_point)]
        )
        assert on_wireframe == pytest.approx(0.0, abs=0.01)
        centre = exploded_anchors[label.text]
        centre_svg = to_svg((centre.dot(right), centre.dot(up)))
        assert distance(leader_points[0]) <= distance(centre_svg) + 0.01


# ------------------------------------------------ callouts and detail views
def _polyline_points(node):
    return [
        tuple(float(value) for value in pair.split(","))
        for pair in node.attrib["points"].split()
    ]


def _polylines(root, stroke_width):
    return [
        _polyline_points(node)
        for node in root.findall("svg:polyline", SVG_NS)
        if node.attrib["stroke-width"] == stroke_width
    ]


def test_callout_leads_from_its_text_to_the_part_it_names(tmp_path):
    output = tmp_path / "callout.svg"
    callout = drawing.Callout(at=(120, 70), to=(80, 30), text="side\n×2",
                              anchor="start")
    render_part_drawing(
        "panel", block(100, 20, 50),
        [ViewSpec("front", callouts=[callout])], 1, output,
    )
    root = ElementTree.parse(output).getroot()

    texts = {node.text: node for node in root.findall("svg:text", SVG_NS)}
    assert {"side", "×2"} <= set(texts)
    # both lines start at the same x and run downward, like exploded labels
    assert texts["side"].attrib["x"] == texts["×2"].attrib["x"]
    assert float(texts["×2"].attrib["y"]) > float(texts["side"].attrib["y"])
    assert texts["side"].attrib["text-anchor"] == "start"

    # the leader is one segment, it starts where the text does, and it is as
    # long as the offset asked for — so the arrow lands on the part, not near it
    leaders = [pl for pl in _polylines(root, "0.35") if len(pl) == 2]
    assert len(leaders) == 1
    start, end = leaders[0]
    assert start == pytest.approx(
        (float(texts["side"].attrib["x"]), float(texts["side"].attrib["y"])),
        abs=0.01,
    )
    assert math.dist(start, end) == pytest.approx(math.hypot(40, 40), abs=0.01)


def test_the_caption_clears_the_bottom_row_of_a_label_under_the_view(tmp_path):
    """A callout runs downward from its anchor, so its *last* row is what the
    caption has to clear. Sizing that clearance off the anchor put a label's
    second row on the caption's line.
    """
    output = tmp_path / "under.svg"
    callout = drawing.Callout(at=(20, -40), to=(50, 10),
                              text="top_rail\nfront\n100×20×18", anchor="start")
    render_part_drawing(
        "panel", block(100, 20, 50),
        [ViewSpec("front", caption="what it is", callouts=[callout])],
        1, output,
    )
    root = ElementTree.parse(output).getroot()

    texts = {node.text: node for node in root.findall("svg:text", SVG_NS)}
    bottom_row = float(texts["100×20×18"].attrib["y"])
    assert float(texts["what it is"].attrib["y"]) > bottom_row


def test_detail_redraws_the_circled_region_magnified_and_clipped(tmp_path):
    output = tmp_path / "detail.svg"
    detail = drawing.Detail(
        centre=(0, 0), radius=8, at=(50, 90), scale=4, label="A",
        caption="detail A",
        dims=[drawing.Dim("aligned", (0, 0), (5, 0), -4, label="5 real")],
    )
    render_part_drawing(
        "panel", block(100, 20, 50),
        [ViewSpec("front", details=[detail])], 1, output,
    )
    root = ElementTree.parse(output).getroot()

    circles = [pl for pl in _polylines(root, "0.25") if len(pl) == 73]
    assert len(circles) == 2
    radii = sorted(
        max(math.dist(point, pl[0]) for point in pl) / 2 for pl in circles
    )
    assert radii == pytest.approx([8, 32], abs=0.01)

    # the magnified copy is inside the big circle and nowhere near the small
    # one: everything outside the region was clipped away, so a corner detail
    # cannot drag the whole part along with it
    big = circles[-1]
    centre = (
        (min(x for x, _ in big) + max(x for x, _ in big)) / 2,
        (min(y for _, y in big) + max(y for _, y in big)) / 2,
    )
    magnified = [
        pl for pl in _polylines(root, "0.5")
        if all(math.dist(point, centre) <= 32.01 for point in pl)
    ]
    assert magnified, "the region was not redrawn inside the detail circle"
    # the part corner is a right angle 8 long each way at 1:1; magnified it is
    # 32, which is what says the geometry went through the same transform
    assert max(
        math.dist(a, b) for pl in magnified for a, b in zip(pl, pl[1:])
    ) == pytest.approx(32, abs=0.01)

    texts = [node.text for node in root.findall("svg:text", SVG_NS)]
    assert "A" in texts and "detail A" in texts and "5 real" in texts


def test_detail_dimensions_must_be_aligned_and_carry_their_real_size(tmp_path):
    def render(dim):
        render_part_drawing(
            "panel", block(100, 20, 50),
            [ViewSpec("front", details=[drawing.Detail(
                centre=(0, 0), radius=8, at=(50, 90), scale=4, dims=[dim],
            )])],
            1, tmp_path / "raises.svg",
        )

    # an "h" dim measures to the part's own edge, and a detail has none
    with pytest.raises(ValueError, match="aligned"):
        render(Dim("h", 0, 5, -4, label="5"))
    # ...and an unlabelled one would print the magnified number as the size
    with pytest.raises(ValueError, match="label"):
        render(Dim("aligned", (0, 0), (5, 0), -4))


def test_sheet_text_scale_lands_the_target_type_size_on_the_page():
    """A sheet scaled into a PDF panel needs its type sized from that ratio.

    The multiplier is what `render_part_drawing` applies to TEXT_SIZE, so
    `TEXT_SIZE * scale` millimetres of model, shrunk by panel/span, must come
    out at the target millimetres of paper.
    """
    span, panel, target = 1500.0, 184.0, 2.6
    scale = drawing.sheet_text_scale(span, panel, target)
    assert TEXT_SIZE * scale * panel / span == pytest.approx(target)
    # 1:1 into its panel is the identity case: 3.5 mm of model prints 2.6 mm.
    assert drawing.sheet_text_scale(184.0, 184.0) == pytest.approx(2.6 / TEXT_SIZE)


@pytest.mark.parametrize(
    "args", [(0, 184.0), (-1500.0, 184.0), (1500.0, 0), (1500.0, -184.0)]
)
def test_sheet_text_scale_rejects_non_positive_inputs(args):
    with pytest.raises(ValueError, match="must all be positive"):
        drawing.sheet_text_scale(*args)
