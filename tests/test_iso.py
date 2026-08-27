"""cadkit.draw.iso — the cheap shape check, on the shared projection."""

from xml.etree import ElementTree

import pytest
from build123d import Box, Pos

from cadkit.draw import iso
from cadkit.draw.drawing import VIEW_DIRS, project_edges, view_basis


def test_iso_writes_a_wireframe_svg(tmp_path):
    out = tmp_path / "part.svg"
    assert iso(Box(20, 10, 5), out) == out
    text = out.read_text()
    assert text.startswith("<svg")
    root = ElementTree.fromstring(text)
    polylines = root.findall("{http://www.w3.org/2000/svg}polyline")
    assert len(polylines) >= 9  # a box shows 9 visible edges from an iso corner


def test_iso_draws_hidden_edges_dashed(tmp_path):
    """A solid box hides three edges; they must be distinguishable from the rest."""
    out = tmp_path / "part.svg"
    iso(Box(20, 10, 5), out)
    text = out.read_text()
    assert "stroke-dasharray" in text


def test_iso_accepts_a_named_view(tmp_path):
    out = tmp_path / "top.svg"
    iso(Box(20, 10, 5), out, "top")
    assert out.read_text().startswith("<svg")


def test_iso_accepts_a_direction_vector(tmp_path):
    """One-off angles go through the same projection, not a second copy of it."""
    out = tmp_path / "angled.svg"
    iso(Box(20, 10, 5), out, VIEW_DIRS["iso"])
    named = tmp_path / "named.svg"
    iso(Box(20, 10, 5), named, "iso")
    assert out.read_text() == named.read_text()


def test_projection_is_normalized_to_the_origin():
    """Every projection starts its own frame at (0, 0), wherever the model sits."""
    for shape in (Box(20, 10, 5), Pos(2000, 0, 0) * Box(20, 10, 5)):
        vis, hid = project_edges(shape, "front")
        xs = [x for pl in vis + hid for x, _ in pl]
        ys = [y for pl in vis + hid for _, y in pl]
        assert min(xs) == pytest.approx(0, abs=1e-9)
        assert min(ys) == pytest.approx(0, abs=1e-9)


def test_geometry_far_from_the_origin_shows_perspective():
    """The camera sits CAMERA_DIST from the ORIGIN, not from the shape.

    So a part 2 m out projects slightly wider than its true size. This is the
    documented reason to centre a shape before drawing it at a magnified
    scale; the assertion pins how much error that trade-off actually costs.
    """
    def width(shape):
        vis, hid = project_edges(shape, "front")
        xs = [x for pl in vis + hid for x, _ in pl]
        return max(xs) - min(xs)

    near = width(Box(20, 10, 5))
    far = width(Pos(2000, 0, 0) * Box(20, 10, 5))
    assert near == pytest.approx(20.0, abs=0.01)
    assert far > near  # perspective, not a bug
    assert far - near < 0.3  # ...and small enough to ignore at 1:1


def test_view_basis_accepts_a_vector():
    right_named, up_named = view_basis("iso")
    right_vec, up_vec = view_basis(VIEW_DIRS["iso"])
    assert tuple(right_named) == pytest.approx(tuple(right_vec))
    assert tuple(up_named) == pytest.approx(tuple(up_vec))
