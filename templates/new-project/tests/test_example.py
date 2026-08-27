"""Copy this file per design. Envelope, no-interference, engagement, domain."""

import itertools

import pytest
from build123d import Compound
from designs import example
from designs.example import DEPTH, WIDTH, T


@pytest.fixture(scope="module")
def design():
    return example.build()


def test_overall_envelope(design):
    bb = Compound(children=list(design.placed.values())).bounding_box()
    assert bb.size.X == pytest.approx(WIDTH, abs=0.01)
    assert bb.size.Y == pytest.approx(DEPTH, abs=0.01)
    assert bb.size.Z == pytest.approx(T, abs=0.01)


def test_no_part_interference(design):
    for (na, a), (nb, b) in itertools.combinations(design.placed.items(), 2):
        assert (a & b).volume == pytest.approx(0, abs=1e-6), f"{na} intersects {nb}"


def test_cutlist_dims(design):
    by_name = {p.name: p for p in design.parts}
    assert by_name["top"].dims() == (WIDTH, DEPTH, T)
