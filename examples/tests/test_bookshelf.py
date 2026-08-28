"""Geometry verification: the tests that replace eyeballing a GUI."""

import itertools

import pytest
from build123d import Compound

from cadkit.wood import CLEARANCE, block
from examples import bookshelf
from examples.bookshelf import DADO_DEPTH, DEPTH, HEIGHT, SHELF_Z, WIDTH, T


@pytest.fixture(scope="module")
def design():
    return bookshelf.build()


def test_overall_envelope(design):
    bb = Compound(children=list(design.placed.values())).bounding_box()
    assert bb.size.X == pytest.approx(WIDTH, abs=0.01)
    assert bb.size.Y == pytest.approx(DEPTH, abs=0.01)
    assert bb.size.Z == pytest.approx(HEIGHT, abs=0.01)


def test_no_part_interference(design):
    """No two placed parts may occupy the same space."""
    for (na, a), (nb, b) in itertools.combinations(design.placed.items(), 2):
        overlap = (a & b).volume
        assert overlap == pytest.approx(0, abs=1e-6), f"{na} intersects {nb}"


def test_shelves_engage_dadoes(design):
    """Each shelf end must sit inside the side's stock envelope (the dado)."""
    left_stock = block(T, DEPTH, HEIGHT)
    right_stock = block(T, DEPTH, HEIGHT, at=(WIDTH - T, 0, 0))
    # engaged depth loses half the clearance on each end
    expected = (DADO_DEPTH - CLEARANCE / 2) * DEPTH * T
    for name, shelf in design.placed.items():
        if not name.startswith("shelf"):
            continue
        for stock in (left_stock, right_stock):
            engaged = (shelf & stock).volume
            assert engaged == pytest.approx(expected, rel=0.01), (
                f"{name} engagement {engaged:.0f} != {expected:.0f}"
            )


def test_dado_fit_clearance(design):
    """Dado width minus shelf thickness must equal the fit clearance."""
    side = design.placed["side_left"]
    stock_volume = T * DEPTH * HEIGHT
    removed = 0.0
    for z in SHELF_Z:
        # cutter spans z - c/2 .. z + T + c/2, clamped to the panel: the top
        # dado is open at the panel's top edge (a rabbet) and removes less
        cut = min(z + T + CLEARANCE / 2, HEIGHT) - max(z - CLEARANCE / 2, 0)
        removed += DADO_DEPTH * DEPTH * cut
    expected = stock_volume - removed
    assert side.volume == pytest.approx(expected, rel=1e-6)


def test_cutlist_dims(design):
    by_name = {p.name: p for p in design.parts}
    assert by_name["side"].qty == 2
    assert by_name["side"].dims() == (HEIGHT, DEPTH, T)
    assert by_name["shelf"].qty == len(SHELF_Z)
    shelf_len = WIDTH - 2 * T + 2 * DADO_DEPTH - CLEARANCE
    assert by_name["shelf"].dims() == (round(shelf_len, 1), DEPTH, T)


def test_declares_the_expected_artifacts(design):
    """The export runner writes what build() declared — check the declaration."""
    declared = {a.filename: a.kind for a in design.artifacts}
    assert declared == {
        "step/bookshelf.step": "step",
        "bookshelf_cutlist.csv": "csv",
        "svg/bookshelf_side.svg": "svg",
        "svg/bookshelf_shelf.svg": "svg",
        "svg/bookshelf_exploded.svg": "svg",
    }
