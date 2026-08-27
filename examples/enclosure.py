"""Reference 3D-printing design: open box + friction-fit lid with inner lip.

Run `uv run python -m examples.enclosure` to export STL + iso SVG (+ G-code
stats if OrcaSlicer is installed) into export/.

Both parts are modelled in PRINT ORIENTATION (bed at z=0): box opening up,
lid plate on the bed with the lip up. Neither needs supports. `seated` holds
the assembled positions, which is what the fit tests intersect.
"""

from pathlib import Path

from build123d import Axis, Box, Pos, chamfer, fillet

from cadkit.core import Design, main
from cadkit.print import CLEARANCE_FIT, fits_bed, material_grams, overhang_faces, slice_stl

# ---------------------------------------------------------------- parameters
INNER_L = 80.0
INNER_W = 50.0
INNER_H = 30.0
WALL = 2.0
FLOOR = 1.6
LID_T = 2.4
LIP_H = 5.0
CORNER_R = 4.0          # outer vertical-edge fillet; inner follows at R - WALL
FOOT_CHAMFER = 0.3      # elephant-foot compensation on bed-contact edges

OUTER_L = INNER_L + 2 * WALL
OUTER_W = INNER_W + 2 * WALL
OUTER_H = INNER_H + FLOOR


def _rounded_box(length, w, h, r):
    """Box with filleted vertical edges, min corner z=0, centered in x/y."""
    b = Pos(0, 0, h / 2) * Box(length, w, h)
    return fillet(b.edges().filter_by(Axis.Z), radius=r)


def build() -> Design:
    lip_l = INNER_L - 2 * CLEARANCE_FIT
    lip_w = INNER_W - 2 * CLEARANCE_FIT

    body = _rounded_box(OUTER_L, OUTER_W, OUTER_H, CORNER_R)
    cavity = Pos(0, 0, FLOOR) * _rounded_box(INNER_L, INNER_W, OUTER_H, CORNER_R - WALL)
    body -= cavity
    body = chamfer(body.edges().group_by(Axis.Z)[0], length=FOOT_CHAMFER)

    lip_r = max(CORNER_R - WALL - CLEARANCE_FIT, 0.5)
    lid = _rounded_box(OUTER_L, OUTER_W, LID_T, CORNER_R)
    lid += Pos(0, 0, LID_T) * _rounded_box(lip_l, lip_w, LIP_H, lip_r)
    lid = chamfer(lid.edges().group_by(Axis.Z)[0], length=FOOT_CHAMFER)

    # seated: lid flipped lip-down onto the box rim
    seated_lid = Pos(0, 0, OUTER_H) * _rounded_box(OUTER_L, OUTER_W, LID_T, CORNER_R)
    seated_lid += Pos(0, 0, OUTER_H - LIP_H) * _rounded_box(lip_l, lip_w, LIP_H, lip_r)

    design = Design("enclosure")
    design.placed = {"box": body, "lid": lid}
    design.seated = {"box": body, "lid": seated_lid}
    for name, part in design.placed.items():
        design.stl(name, part)
        design.iso(name, part)
    design.meta = {
        name: {
            "solid_pla_g": round(material_grams(part), 1),
            "fits_bed": fits_bed(part),
            "support_faces": len(overhang_faces(part)),
        }
        for name, part in design.placed.items()
    }
    return design


def report(design: Design, outdir="export") -> None:
    """Print the printability numbers, and slice if OrcaSlicer is installed."""
    for name, facts in design.meta.items():
        print(
            f"{name}: ~{facts['solid_pla_g']:.0f} g solid PLA, "
            f"bed fit: {facts['fits_bed']}, support-needing faces: {facts['support_faces']}"
        )
        stl = Path(outdir) / f"{design.name}_{name}.stl"
        stats = slice_stl(stl, outdir) if stl.exists() else None
        if stats:
            print(f"  sliced: {stats}")


if __name__ == "__main__":
    report(main(build))
