"""The ``cadkit`` console script: snapshot, diff, probe, export.

Run from inside a project folder — the one that holds the plan doc, ``cad/``
and the exported artifacts. Before cadkit this was
``uv run python ../tools/visual_diff.py``, a relative path that only worked
from a sibling directory.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from cadkit import verify

EXPORT = Path(".")  # the project folder is the export directory
GOLDEN = Path(".golden")


def _load_design(module_name: str):
    """Import a design module from the current project and build it."""
    if "" not in sys.path:
        sys.path.insert(0, "")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        raise SystemExit(
            f"cannot import {module_name!r} ({error}) — run from the project's cad/ "
            f"directory, and name the module as you would import it, e.g. arvi_desk"
        ) from error
    if not hasattr(module, "build"):
        raise SystemExit(f"{module_name} has no build() — not a design module")
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cadkit", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="accept the current export/ as the visual baseline")
    p_snap.add_argument("filters", nargs="*", help="artifact filename substrings")

    p_diff = sub.add_parser("diff", help="report which exported pages changed since the baseline")
    p_diff.add_argument("filters", nargs="*", help="artifact filename substrings")

    p_probe = sub.add_parser("probe", help="evaluate an expression against a built design")
    p_probe.add_argument("module", help="design module, e.g. arvi_desk")
    p_probe.add_argument("expr", help="expression over placed/parts/seated/design")

    p_export = sub.add_parser("export", help="run a design module's export")
    p_export.add_argument("module", help="design module, e.g. arvi_desk")
    p_export.add_argument("rest", nargs=argparse.REMAINDER, help="flags passed to the design")

    args = parser.parse_args(argv)

    if args.cmd in ("snapshot", "diff"):
        if not verify.artifacts(EXPORT, []):
            raise SystemExit(
                "no .svg or .pdf here — run from inside a project folder, "
                "and export it first"
            )
        if args.cmd == "snapshot":
            verify.snapshot(EXPORT, GOLDEN, args.filters)
        else:
            print("\n".join(verify.diff(EXPORT, GOLDEN, args.filters)))
        return 0

    module = _load_design(args.module)
    if args.cmd == "probe":
        from cadkit.core import probe

        print(probe(module.build(), args.expr))
        return 0

    from cadkit.core import main as run_export

    run_export(module.build, args.rest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
