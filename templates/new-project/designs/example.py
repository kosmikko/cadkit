"""Rename this module and make it your first design.

The shape of a design module: parameters as constants at the top so a
dimension change is a one-line edit; `build()` returning a `Design` that
declares its artifacts; `main(build)` at the bottom so the module is runnable.
"""

from cadkit.core import Design, main
from cadkit.wood import Part, block

# ---------------------------------------------------------------- parameters
WIDTH = 400.0
DEPTH = 300.0
T = 18.0


def build() -> Design:
    top = block(WIDTH, DEPTH, T)

    design = Design("example")
    design.placed = {"top": top}
    design.parts = [Part("top", top)]
    design.step()
    design.cutlist()
    return design


if __name__ == "__main__":
    main(build)
