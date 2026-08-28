# cadkit

Code-CAD for build123d: model parts in Python, verify geometry with pytest
assertions, export headlessly. Woodworking gets STEP + dimensioned SVG shop
drawings + cut lists; 3D printing gets STL + printability checks + an optional
slicer stage. Units are mm throughout.

One repo, two faces — a **Python package** and a **Claude Code plugin**. One
clone, one version number, so the knowledge and the code it describes cannot
drift apart.

## Install

```bash
# macOS
brew install uv
# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Nothing else is needed: uv manages Python itself, and build123d bundles the
OCCT kernel (prebuilt wheels for macOS arm64/x86_64 and Linux). For 3D
printing, optionally `brew install --cask orcaslicer` — it only enables print
time and filament estimates.

```bash
git clone https://github.com/kosmikko/cadkit && cd cadkit
uv sync          # ~1 min, big wheels
uv run pytest -q
```

If `uv sync` fails on the Python version: the project pins `>=3.11,<3.13`
because build123d wheels lag new Python releases. Let uv fetch 3.12
(`uv python install 3.12`).

## Try it

```bash
uv run python -m examples.bookshelf    # STEP, cut list, part sheets, exploded view
uv run python -m examples.enclosure    # STL + iso preview, printability numbers
ls export/
```

Then look at the output, which is half of the workflow rule below:

```bash
# macOS — note: qlmanage square-crops non-square sheets; split the SVG
# viewBox into halves first for tall or wide ones
qlmanage -t -s 1000 -o /tmp export/bookshelf_exploded.svg
# Linux
rsvg-convert -w 1000 export/bookshelf_exploded.svg -o /tmp/exploded.png
```

The exploded view shows 2 side panels + 4 shelves, labels on the correct
parts — `side_left` is the panel whose dado grooves face the camera. The same
check runs as an assertion in `examples/tests/test_export_pipeline.py`.

## Use it in a project

Copy `templates/new-project/` and rename it. It sets up one folder per thing
you are building — plan doc, `cad/` sources and exported output together —
with a root `conftest.py` that puts every project's `cad/` on `sys.path`, so
`uv run pytest` from the top runs every suite:

```
example/
  example-plan.md  example_cutlist.csv  example_summary.json
  cad/example.py  cad/tests/test_example.py
  svg/  step/  .golden/
```

The project folder *is* the export directory: `Design` sorts artifacts into
subfolders by kind (`LAYOUT = {"svg": "svg", "step": "step"}`, overridable via
`Design(name, layout=...)`), leaving the shop PDF, the cut list and the STL —
the things you actually pick up — at the root.

The dependency is a git tag, so
`uv.lock` pins it; the path override lets you iterate on cadkit and the design
in one edit-test cycle when the repos are checked out as siblings.

```toml
dependencies = ["cadkit @ git+https://github.com/kosmikko/cadkit@v0.2.0"]

[tool.uv.sources]  # local dev override; comment out to use the pinned tag
cadkit = { path = "../cadkit", editable = true }
```

## The package

| Module | What |
|---|---|
| `cadkit.core` | `Design`, the export runner (`--only` / `--skip-<kind>`), `probe`, `summary.json` |
| `cadkit.draw` | HLR projection → SVG: `Dim`, `ViewSpec`, part sheets, exploded views, `iso()`, `PdfReport` |
| `cadkit.wood` | `block()`, `dado()`, `Part` → CSV cut lists, sheet nesting, cut-plan sheets |
| `cadkit.print` | `BED`, FDM clearances, `overhang_faces()`, `fits_bed()`, OrcaSlicer stage |
| `cadkit.verify` | Golden-PNG visual diff, behind the `cadkit` console script |

A design **declares** what it produces and the runner **executes** it. That
split is what makes `--only` and `--skip-pdf` possible, and it means
`<name>_summary.json` — per-part dims, positions, volumes, bboxes — is written
whether or not the artifacts were:

```python
from cadkit.core import Design, main

def build() -> Design:
    d = Design("bookshelf")
    d.placed = {"side_left": side, ...}      # solids in canonical positions
    d.parts = [Part("side", side, qty=2)]    # cut-list entries
    d.step(); d.cutlist(); d.exploded(explode=0.9)
    d.drawing("side", side, side_views, qty=2)
    return d

if __name__ == "__main__":
    main(build)
```

## The CLI

```bash
# from inside a project folder
uv run cadkit snapshot            # accept the current output as the visual baseline
uv run cadkit diff                # report which pages actually changed
# from inside its cad/
uv run cadkit probe shelf "placed['side'].volume"
uv run cadkit export shelf --only side --skip-pdf --outdir ..
```

## The plugin

`skills/` holds four Claude Code skills, loaded on demand rather than every
session:

| Skill | Covers |
|---|---|
| `build123d` | The cheatsheet, selector idioms, and the verified gotchas. **THIS IS NOT CadQuery.** |
| `shop-drawings` | Dims, sheets, exploded views, cut lists, nesting, PDF packages |
| `printability` | Print orientation, overhangs, clearances, bed fit, slicer |
| `cad-iterate` | Scoped tests → scoped export → visual diff → look |

**One rule deliberately stays out of the skills.** Skills load on a
probabilistic trigger match, and this is the rule that has actually caught
bugs both ways — a volume test caught wrong geometry, and only the vision
check caught a mirrored label frame. It belongs in every consuming project's
always-loaded `CLAUDE.md` (see `templates/new-project/CLAUDE.md`):

> Code-CAD with build123d, units mm. Never claim a design done without
> (1) `uv run pytest -q` passing and (2) rendering the export and looking at
> it. Before writing geometry, read the `build123d` skill. NOT CadQuery.

## Optional: a human 3D viewer

For a live 3D view while iterating (the agent does not need it): install the
"OCP CAD Viewer" VS Code extension. `ocp-vscode` is already a dev dependency.

## License

MIT.
