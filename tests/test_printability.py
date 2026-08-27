"""Unit tests for the printability checks themselves — trust but verify."""

from build123d import Axis, Box, Pos, chamfer

from cadkit.print import drop_to_bed, fits_bed, overhang_faces


def _bedded_box(*dims):
    return drop_to_bed(Box(*dims))


def test_plain_box_has_no_overhangs():
    assert overhang_faces(_bedded_box(20, 20, 10)) == []


def test_side_notch_ceiling_is_flagged():
    part = _bedded_box(40, 20, 20)
    # notch into the +x side at mid-height: its ceiling faces straight down
    part -= Pos(15, 0, 8) * Box(20, 30, 6)
    flagged = overhang_faces(part)
    assert len(flagged) == 1
    assert flagged[0].normal_at().Z < -0.99


def test_elevated_table_underside_is_flagged():
    # mushroom: pedestal on the bed, wider plate on top — the plate's
    # underside ring is horizontal but NOT at bed level, so it needs support
    part = _bedded_box(10, 10, 15)
    part += Pos(0, 0, 17.5) * Box(30, 30, 5)
    flagged = overhang_faces(part)
    assert len(flagged) == 1
    assert flagged[0].bounding_box().min.Z == 15.0


def test_45_degree_chamfer_is_printable():
    # 45° bottom chamfer sits exactly on the printable limit — no support
    part = _bedded_box(20, 20, 10)
    part = chamfer(part.edges().group_by(Axis.Z)[0], length=3)
    assert overhang_faces(part, max_overhang_deg=45) == []
    # but a stricter printer profile (e.g. 40° limit) must flag it
    assert len(overhang_faces(part, max_overhang_deg=40)) >= 4


def test_fits_bed_allows_rotation():
    assert fits_bed(_bedded_box(200, 100, 50), bed=(220, 220, 250))
    assert fits_bed(_bedded_box(100, 215, 50), bed=(220, 220, 250))
    assert not fits_bed(_bedded_box(230, 100, 50), bed=(220, 220, 250))
    assert not fits_bed(_bedded_box(100, 100, 260), bed=(220, 220, 250))
