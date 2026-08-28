"""The shared spine of a design module: ``Design``, the export runner, probe.

Before cadkit, every design module carried its own copy of a ``Design``
dataclass and its own ``export_all``. They drifted, and one of them ended up
importing ``Design`` from a sibling design to avoid a ninth copy. This is the
one copy.

A design **declares** what it produces and the runner **executes** it. That
split is what makes ``--only`` and ``--skip-pdf`` possible: the runner can see
the whole artifact list before writing any of it, so it can filter, report what
it skipped, and record the geometry in ``<name>_summary.json`` either way.

A design module lives in its project folder's ``cad/`` and looks like::

    from cadkit.core import Design, main

    def build() -> Design:
        d = Design("bookshelf")
        d.placed = {"side_left": side_left, "shelf_1": shelf, ...}
        d.parts = [Part("side", side_left, qty=2)]
        d.step()
        d.cutlist()
        d.drawing("side", side_left, side_views, qty=2)
        d.exploded(explode=0.9)
        return d

    if __name__ == "__main__":
        main(build)

Units are mm. Furniture puts parts in assembly coordinates; printing puts them
in print orientation with the bed at z=0 and uses ``seated`` for the assembled
positions that fit tests need.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

#: Artifact kinds the runner understands. ``--skip-<kind>`` works for each.
KINDS = ("step", "stl", "svg", "csv", "md", "pdf", "json")

#: Where each kind lands under the output directory. A project folder holds the
#: output you actually pick up — the shop PDF, the cut list, the STL — at its
#: root, and files down the subfolders in this map. Kinds absent from the map
#: stay at the root. Override per design with ``Design(name, layout={...})``.
LAYOUT = {"svg": "svg", "step": "step"}


@dataclass(frozen=True)
class Artifact:
    """One output file, declared now and written later by the runner."""

    name: str  # what it is about: a part name, or "" for the whole design
    kind: str  # one of KINDS
    filename: str  # relative to outdir
    write: Callable[[Path], None]

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown artifact kind {self.kind!r}, expected one of {KINDS}")


@dataclass
class Design:
    """Everything a design produces, plus the geometry the tests assert on.

    ``placed``  name -> solid in the design's canonical positions: assembly
                coordinates for furniture, print orientation (bed at z=0) for
                3D printing.
    ``parts``   cut-list ``Part`` entries — unique parts with quantities, not
                one entry per placed solid. Empty for prints.
    ``seated``  assembled positions, when those differ from ``placed``. A
                printed lid is modelled flat on the bed and seated on the box;
                the no-interference tests run against ``seated``.
    ``meta``    anything a test or a plan doc wants echoed into the summary.
    ``layout``  kind -> subdirectory, defaulting to :data:`LAYOUT`.
    """

    name: str
    placed: dict = field(default_factory=dict)
    parts: list = field(default_factory=list)
    seated: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    layout: dict[str, str] = field(default_factory=lambda: dict(LAYOUT))

    # ------------------------------------------------------------- declaring

    def add(self, name: str, kind: str, filename: str, write) -> Artifact:
        """Declare an arbitrary artifact. The convenience methods below wrap this.

        The layout prefix is applied here rather than in each convenience
        method, so it covers the call sites that pass an explicit ``filename``
        too — assembly sheets, cut-plan sheets, a fixed-name STEP.
        """
        subdir = self.layout.get(kind)
        if subdir:
            filename = f"{subdir}/{filename}"
        art = Artifact(name, kind, filename, write)
        self.artifacts.append(art)
        return art

    def _stem(self, suffix: str = "") -> str:
        return f"{self.name}_{suffix}" if suffix else self.name

    def step(self, shapes=None, *, name: str = "", filename: str | None = None):
        """A STEP assembly of `shapes` (default: everything in ``placed``)."""
        filename = filename or f"{self._stem(name)}.step"

        def write(path):
            from build123d import Compound, export_step

            solids = shapes if shapes is not None else list(self.placed.values())
            if isinstance(solids, dict):
                solids = list(solids.values())
            export_step(Compound(children=list(solids)), str(path))

        return self.add(name or self.name, "step", filename, write)

    def stl(self, name: str, shape, *, filename: str | None = None):
        """A mesh export of one part, for printing."""
        filename = filename or f"{self._stem(name)}.stl"

        def write(path):
            from build123d import export_stl

            export_stl(shape, str(path))

        return self.add(name, "stl", filename, write)

    def iso(self, name: str, shape, *, view: str = "iso", filename: str | None = None):
        """A quick isometric wireframe SVG — the shape check, not a drawing."""
        filename = filename or f"{self._stem(name)}.svg"

        def write(path):
            from cadkit.draw import iso as render_iso

            render_iso(shape, str(path), view)

        return self.add(name, "svg", filename, write)

    def drawing(self, name: str, shape, views, qty: int = 1, *, filename: str | None = None,
                **kwargs):
        """A dimensioned part sheet: orthographic views laid out left to right."""
        filename = filename or f"{self._stem(name)}.svg"

        def write(path):
            from cadkit.draw import render_part_drawing

            render_part_drawing(name, shape, views, qty, str(path), **kwargs)

        return self.add(name, "svg", filename, write)

    def exploded(self, *, explode: float = 0.9, placed=None, name: str = "exploded",
                 filename: str | None = None, **kwargs):
        """An exploded isometric of the assembly, parts labelled with cut sizes."""
        filename = filename or f"{self._stem(name)}.svg"

        def write(path):
            from cadkit.draw import render_exploded

            render_exploded(placed if placed is not None else self.placed,
                            explode=explode, path=str(path), **kwargs)

        return self.add(name, "svg", filename, write)

    def cutlist(self, *, name: str = "cutlist", filename: str | None = None):
        """The cut list as CSV. Requires ``parts``."""
        filename = filename or f"{self._stem(name)}.csv"

        def write(path):
            from cadkit.wood.cutlist import write_csv

            if not self.parts:
                raise ValueError(f"{self.name}: cutlist() declared but parts is empty")
            write_csv(self.parts, path)

        return self.add(name, "csv", filename, write)

    def pdf(self, build_pdf, *, name: str = "package", filename: str | None = None):
        """A PDF package. `build_pdf(path)` composes and saves it.

        Declared as kind "pdf" so ``--skip-pdf`` can drop it: PDF packages are
        the slowest artifact and the most expensive to re-inspect.
        """
        filename = filename or f"{self._stem(name)}.pdf"
        return self.add(name, "pdf", filename, build_pdf)

    # -------------------------------------------------------------- geometry

    def summary(self) -> dict:
        """Machine-readable geometry: dims, positions, volumes, bboxes.

        Read this instead of probing with ``python -c`` or rereading the source
        to answer "how long is rafter_3 now?".
        """
        out = {
            "design": self.name,
            "units": "mm",
            "placed": {name: _shape_summary(s) for name, s in self.placed.items()},
            "artifacts": [
                {"name": a.name, "kind": a.kind, "file": a.filename} for a in self.artifacts
            ],
        }
        if self.seated:
            out["seated"] = {name: _shape_summary(s) for name, s in self.seated.items()}
        if self.parts:
            from cadkit.wood.cutlist import rows

            out["cutlist"] = rows(self.parts)
        if self.meta:
            out["meta"] = self.meta
        return out


def _shape_summary(shape) -> dict:
    bb = shape.bounding_box()
    return {
        "bbox_min": [round(v, 3) for v in (bb.min.X, bb.min.Y, bb.min.Z)],
        "bbox_max": [round(v, 3) for v in (bb.max.X, bb.max.Y, bb.max.Z)],
        "size": [round(v, 3) for v in (bb.size.X, bb.size.Y, bb.size.Z)],
        "center": [round(v, 3) for v in (bb.center().X, bb.center().Y, bb.center().Z)],
        "volume": round(shape.volume, 3),
    }


# ------------------------------------------------------------------- running


def export_all(design: Design, outdir="export", *, only=(), skip=(), summary=True,
               quiet=False) -> list[str]:
    """Write the design's declared artifacts; return the filenames written.

    ``only``  keep artifacts whose name or filename contains any of these
              substrings. Everything else is skipped, and said to be skipped.
    ``skip``  artifact kinds to drop, e.g. ``("pdf",)``.

    The summary is written whichever artifacts ran, because it is derived from
    the model rather than from the files — a scoped export still answers
    "what are the dimensions now?".
    """
    out = Path(outdir)
    os.makedirs(out, exist_ok=True)
    written, skipped = [], []
    for art in design.artifacts:
        if art.kind in skip:
            skipped.append(f"{art.filename} (--skip-{art.kind})")
            continue
        if only and not any(f in art.name or f in art.filename for f in only):
            skipped.append(f"{art.filename} (not in --only)")
            continue
        path = out / art.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        art.write(path)
        written.append(art.filename)
    if summary:
        path = out / f"{design.name}_summary.json"
        path.write_text(json.dumps(design.summary(), indent=1) + "\n")
        written.append(path.name)
    if not quiet:
        for name in written:
            print(f"  wrote {out}/{name}")
        if skipped:
            print(f"  skipped {len(skipped)}: {', '.join(skipped)}")
    return written


def probe(design: Design, expr: str):
    """Evaluate `expr` against the built design. Kills the python -c one-liners.

    Names in scope: ``design``, ``placed``, ``parts``, ``seated``, plus the
    build123d namespace, so ``placed['side_left'].volume`` and
    ``(placed['a'] & placed['b']).volume`` both work.
    """
    import build123d

    scope = dict(vars(build123d))
    scope.update(
        design=design,
        placed=design.placed,
        parts=design.parts,
        seated=design.seated,
        summary=design.summary,
    )
    return eval(expr, scope)  # a developer tool: the expression is typed by the developer


def main(build: Callable[[], Design], argv=None, *, outdir: str = ".") -> Design:
    """Entry point for ``python cad/<name>.py``. Returns the built design.

    ``outdir`` defaults to the current directory because a project folder *is*
    its export directory: run the design from the folder that holds its plan
    doc and the artifacts land beside it, sorted into subfolders by
    :data:`LAYOUT`.
    """
    parser = argparse.ArgumentParser(description=(build.__doc__ or "export a design").strip())
    parser.add_argument("--outdir", default=outdir,
                        help=f"output directory (default: {outdir})")
    parser.add_argument("--only", action="append", default=[], metavar="SUBSTR",
                        help="only artifacts matching this substring; repeatable")
    parser.add_argument("--no-summary", action="store_true",
                        help="do not write <name>_summary.json")
    parser.add_argument("--probe", metavar="EXPR",
                        help="build, print eval(EXPR) against the design, and exit")
    for kind in KINDS:
        parser.add_argument(f"--skip-{kind}", action="store_true",
                            help=f"skip {kind} artifacts")
    args = parser.parse_args(argv)

    design = build()
    if args.probe:
        print(probe(design, args.probe))
        return design

    skip = tuple(k for k in KINDS if getattr(args, f"skip_{k}"))
    print(f"{design.name}: {len(design.artifacts)} artifact(s) declared")
    export_all(design, args.outdir, only=tuple(args.only), skip=skip,
               summary=not args.no_summary)
    return design


if __name__ == "__main__":  # pragma: no cover - `python -m cadkit.core` is not a design
    sys.exit("cadkit.core is a library; run a design module instead")
