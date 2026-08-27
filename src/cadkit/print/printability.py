"""Printability checks for FDM — the printing analog of furniture's joinery tests.

Convention: parts are modeled in PRINT ORIENTATION with the bed at z=0
(use drop_to_bed() after construction if needed).
"""

from __future__ import annotations

import math

# Adjust to the actual printer (x, y, z build volume in mm).
BED = (175, 180, 170)  # Qidi Tech X-Smart 3

# FDM fit clearances per side, verified against printed reality per printer/
# material — start here, tune after a tolerance test print. Holes shrink and
# x/y needs more room than z.
CLEARANCE_PRESS = 0.1   # press fit, needs force
CLEARANCE_FIT = 0.2     # snug sliding fit (lids, sleeves)
CLEARANCE_FREE = 0.4    # loose fit, moving parts

PLA_DENSITY_G_CM3 = 1.24


def drop_to_bed(part):
    """Translate part so its lowest point sits on z=0."""
    from build123d import Pos

    return Pos(0, 0, -part.bounding_box().min.Z) * part


def fits_bed(part, bed=BED) -> bool:
    """True if the part fits the build volume (allows 90° rotation on bed)."""
    s = part.bounding_box().size
    if s.Z > bed[2]:
        return False
    return (s.X <= bed[0] and s.Y <= bed[1]) or (s.X <= bed[1] and s.Y <= bed[0])


def overhang_faces(part, max_overhang_deg: float = 45.0) -> list:
    """Faces that would need support at the given overhang limit.

    A face needs support when it points downward more steeply than the
    printable overhang angle: normal.Z < -sin(max_overhang_deg). Horizontal
    faces sitting at bed level are bed contact, not overhangs. Curved faces
    are judged by their center normal — good enough for functional parts.
    """
    threshold = -math.sin(math.radians(max_overhang_deg)) - 1e-9
    zmin = part.bounding_box().min.Z
    flagged = []
    for face in part.faces():
        try:
            n = face.normal_at()
        except Exception:
            continue  # degenerate face; boolean-op artifact
        on_bed = n.Z < -0.999 and face.bounding_box().min.Z <= zmin + 1e-6
        if n.Z < threshold and not on_bed:
            flagged.append(face)
    return flagged


def material_grams(part, infill: float = 1.0, density=PLA_DENSITY_G_CM3) -> float:
    """Rough filament estimate. infill=1.0 gives the solid upper bound;
    real prints with walls + 15-40% infill land well below it."""
    return part.volume / 1000.0 * density * infill
