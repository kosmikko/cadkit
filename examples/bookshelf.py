"""Reference woodworking design: two sides, four shelves housed in dadoes.

The small end-to-end example — copy its structure for a new piece. Run
`uv run python -m examples.bookshelf` to export STEP + cut list + drawings
into export/, or add `--only side` / `--skip-svg` to scope the loop.

Axes: x = width, y = depth (front->back), z = height. Origin at
front-bottom-left of the assembled unit. All dims in mm.
"""

from cadkit.core import Design, main
from cadkit.draw import Dim, ViewSpec
from cadkit.wood import CLEARANCE, Part, block, dado

# ---------------------------------------------------------------- parameters
WIDTH = 800
HEIGHT = 900
DEPTH = 250
T = 18  # sheet stock thickness
DADO_DEPTH = 6
SHELF_Z = [60, 340, 620, HEIGHT - T]  # bottom face of each shelf


def build() -> Design:
    shelf_len = WIDTH - 2 * T + 2 * DADO_DEPTH - CLEARANCE

    side_left = block(T, DEPTH, HEIGHT)
    for z in SHELF_Z:
        side_left = dado(side_left, width=T, depth=DADO_DEPTH,
                         at=(T - DADO_DEPTH, 0, z))

    side_right = block(T, DEPTH, HEIGHT, at=(WIDTH - T, 0, 0))
    for z in SHELF_Z:
        side_right = dado(side_right, width=T, depth=DADO_DEPTH,
                          at=(WIDTH - T, 0, z))

    shelves = {
        f"shelf_{i + 1}": block(
            shelf_len, DEPTH, T, at=(T - DADO_DEPTH + CLEARANCE / 2, 0, z)
        )
        for i, z in enumerate(SHELF_Z)
    }

    design = Design("bookshelf")
    design.placed = {"side_left": side_left, "side_right": side_right, **shelves}
    design.parts = [
        Part("side", side_left, qty=2, note=f"4 dadoes {DADO_DEPTH} deep"),
        Part("shelf", shelves["shelf_1"], qty=len(SHELF_Z)),
    ]

    # --- drawings: side gets a face view (dado positions) + edge view (depths)
    side_views = [
        ViewSpec(
            "right",  # looking at the inner face of the left side: D wide, H tall
            caption="inner face",
            dims=[
                Dim("v", 0, HEIGHT, -14),
                Dim("h", 0, DEPTH, -10),
                # dado bottoms from part bottom edge, staggered to stay readable
                *[
                    Dim("v", 0, z, DEPTH + 12 + 11 * i)
                    for i, z in enumerate(SHELF_Z)
                ],
            ],
        ),
        ViewSpec(
            "front",  # edge-on: T wide, H tall, dado notches visible
            caption="front edge",
            dims=[
                Dim("h", 0, T, -10),
                Dim("h", T - DADO_DEPTH, T, HEIGHT + 8),
            ],
        ),
    ]
    shelf_views = [
        ViewSpec(
            "top",
            caption="top",
            dims=[Dim("h", 0, shelf_len, -10), Dim("v", 0, DEPTH, -14)],
        ),
        ViewSpec("front", caption="front edge", dims=[Dim("v", 0, T, -14)]),
    ]

    design.step()
    design.cutlist()
    design.drawing("side", side_left, side_views, qty=2)
    design.drawing("shelf", shelves["shelf_1"], shelf_views, qty=len(SHELF_Z))
    design.exploded(explode=0.9)
    return design


if __name__ == "__main__":
    main(build)
