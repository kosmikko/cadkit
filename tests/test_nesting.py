"""Contract for the strip nester: a layout you can actually take to a saw."""

import pytest

from cadkit.wood import Piece, nest

PANEL_L = 1525
PANEL_W = 1220
KERF = 3


def plan(pieces, **kwargs):
    return nest(pieces, panel_length=kwargs.get("panel_length", PANEL_L),
                panel_width=kwargs.get("panel_width", PANEL_W),
                kerf=kwargs.get("kerf", KERF))


def gap(a0, a1, b0, b1):
    """Clear distance between two spans; negative if they overlap."""
    return max(b0 - a1, a0 - b1)


def test_every_piece_is_placed_exactly_once():
    pieces = [Piece(f"p{i}", 400, 300) for i in range(10)]
    placed = [p.name for p in plan(pieces).placements]
    assert sorted(placed) == sorted(p.name for p in pieces)


def test_nothing_hangs_off_the_panel():
    pieces = [Piece("wide", 1500, 600), Piece("tall", 1200, 700),
              Piece("small", 300, 90)]
    result = plan(pieces)
    for panel in result.panels:
        for p in panel.placements:
            assert p.x >= -1e-9
            assert p.y >= -1e-9
            assert p.x + p.length <= result.panel_length + 1e-6
            assert p.y + p.width <= result.panel_width + 1e-6


def test_no_two_parts_are_closer_than_the_kerf():
    """A blade has width; a layout that ignores it cuts the neighbour short.

    Two parts may abut on one axis only if they are a kerf apart on the other,
    so the separation on at least one axis has to clear the blade.
    """
    pieces = [Piece("a", 700, 550), Piece("b", 600, 550), Piece("c", 500, 550),
              Piece("d", 500, 500), Piece("e", 500, 500), Piece("f", 900, 430),
              Piece("g", 400, 80), Piece("h", 400, 80)]
    result = plan(pieces)
    for panel in result.panels:
        placements = panel.placements
        for i, a in enumerate(placements):
            for b in placements[i + 1:]:
                along = gap(a.x, a.x + a.length, b.x, b.x + b.length)
                across = gap(a.y, a.y + a.width, b.y, b.y + b.width)
                assert max(along, across) >= KERF - 1e-6, (a, b)


def test_parts_that_share_a_width_share_a_strip():
    """The whole point: one rip setting, then crosscuts off that strip."""
    pieces = [Piece(f"board{i}", 400, 550) for i in range(3)]
    result = plan(pieces)
    assert len(result.panels) == 1
    strips = result.panels[0].strips
    assert len(strips) == 1
    assert strips[0].width == pytest.approx(550)
    assert len(strips[0].placements) == 3


def test_a_wide_part_does_not_swallow_the_narrow_ones():
    """Membership is an exact width match, not "fits inside".

    Scoring candidate widths by area alone lets the widest strip claim every
    part, score best, and waste most of its own width — six panels where three
    would do. This is that regression.
    """
    pieces = [Piece("slab", 400, 900)] + [Piece(f"rail{i}", 500, 80)
                                          for i in range(8)]
    result = plan(pieces)
    widths = sorted({s.width for panel in result.panels for s in panel.strips})
    # the rails get their own 80 strips, and the slab is ripped to 400 rather
    # than 900 because turning it costs 500 less of the panel's width
    assert widths == [80, 400]
    assert len(result.panels) == 1


def test_a_piece_bigger_than_a_panel_is_refused():
    """Silently dropping it would be a cut list that does not add up."""
    with pytest.raises(ValueError, match="does not fit"):
        plan([Piece("desk_top", 2400, 550)])
    # ...and it fits once rotated into range
    plan([Piece("long", 1500, 1200)])


def test_rotation_is_used_when_it_helps():
    piece = Piece("board", 1200, 500)
    result = plan([piece], panel_length=600, panel_width=1300)
    placed = result.placements[0]
    assert (placed.length, placed.width) == pytest.approx((500, 1200))


def test_utilisation_and_cut_count_describe_the_layout():
    pieces = [Piece("a", 1525, 610), Piece("b", 1525, 610)]
    result = plan(pieces, kerf=0)
    assert len(result.panels) == 1
    assert result.utilisation == pytest.approx(1.0)
    # one rip to split the panel, then a crosscut to free each part
    assert result.cut_count == 1 + 2


def test_empty_input_is_a_plan_with_no_panels():
    result = plan([])
    assert result.panels == []
    assert result.placements == []
