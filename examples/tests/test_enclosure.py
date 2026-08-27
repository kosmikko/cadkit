"""Geometry verification for the enclosure reference design."""

import math

import pytest

from cadkit.print import CLEARANCE_FIT, fits_bed, overhang_faces
from examples import enclosure
from examples.enclosure import (
    CORNER_R,
    FLOOR,
    INNER_H,
    INNER_L,
    INNER_W,
    LID_T,
    LIP_H,
    OUTER_H,
    OUTER_L,
    OUTER_W,
    WALL,
)


@pytest.fixture(scope="module")
def design():
    return enclosure.build()


def _rounded_rect_area(length, w, r):
    return length * w - (4 - math.pi) * r * r


def test_lid_does_not_collide_when_seated(design):
    box, lid = design.seated["box"], design.seated["lid"]
    assert (box & lid).volume == pytest.approx(0, abs=1e-6)


def test_lip_engages_cavity(design):
    # the seated lip must occupy the cavity: intersect lid with the box's
    # stock envelope (outer rounded box, no cavity cut)
    envelope = enclosure._rounded_box(OUTER_L, OUTER_W, OUTER_H, CORNER_R)
    lip_l = INNER_L - 2 * CLEARANCE_FIT
    lip_w = INNER_W - 2 * CLEARANCE_FIT
    lip_r = max(CORNER_R - WALL - CLEARANCE_FIT, 0.5)
    expected = _rounded_rect_area(lip_l, lip_w, lip_r) * LIP_H
    engaged = (design.seated["lid"] & envelope).volume
    assert engaged == pytest.approx(expected, rel=0.01)


def test_wall_and_floor_from_volume(design):
    body = design.placed["box"]
    outer = _rounded_rect_area(OUTER_L, OUTER_W, CORNER_R) * OUTER_H
    cavity = _rounded_rect_area(INNER_L, INNER_W, CORNER_R - WALL) * INNER_H
    # foot chamfer removes a sliver; allow 1%
    assert body.volume == pytest.approx(outer - cavity, rel=0.01)
    assert FLOOR == pytest.approx(OUTER_H - INNER_H)


def test_print_orientation_needs_no_support(design):
    for name, part in design.placed.items():
        assert part.bounding_box().min.Z == pytest.approx(0, abs=1e-9), name
        assert overhang_faces(part) == [], f"{name} needs support"


def test_parts_fit_bed(design):
    for name, part in design.placed.items():
        assert fits_bed(part), name


def test_lid_height(design):
    assert design.placed["lid"].bounding_box().size.Z == pytest.approx(LID_T + LIP_H)


def test_exports_render(design, tmp_path):
    from build123d import export_stl

    from cadkit.draw import iso

    for name, part in design.placed.items():
        stl = tmp_path / f"{name}.stl"
        export_stl(part, str(stl))
        assert stl.stat().st_size > 1000
        svg = tmp_path / f"{name}.svg"
        iso(part, svg)
        assert svg.read_text().startswith("<svg")
