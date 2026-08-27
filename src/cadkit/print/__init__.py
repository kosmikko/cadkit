"""FDM 3D printing: printability checks and the optional slicer stage.

Parts are modelled in PRINT ORIENTATION with the bed at z=0 — use
``drop_to_bed()`` after construction if the geometry ended up elsewhere.

Import this as ``cadkit.print`` or ``from cadkit.print import ...``. Never
``from cadkit import print``: that shadows the builtin in the importing
module.
"""

from cadkit.print.printability import (
    BED,
    CLEARANCE_FIT,
    CLEARANCE_FREE,
    CLEARANCE_PRESS,
    PLA_DENSITY_G_CM3,
    drop_to_bed,
    fits_bed,
    material_grams,
    overhang_faces,
)
from cadkit.print.slicing import find_slicer, parse_gcode_stats, slice_stl

__all__ = [
    "BED",
    "CLEARANCE_FIT",
    "CLEARANCE_FREE",
    "CLEARANCE_PRESS",
    "PLA_DENSITY_G_CM3",
    "drop_to_bed",
    "find_slicer",
    "fits_bed",
    "material_grams",
    "overhang_faces",
    "parse_gcode_stats",
    "slice_stl",
]
