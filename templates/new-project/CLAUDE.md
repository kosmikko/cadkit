Code-CAD with build123d, units mm. Never claim a design done without
(1) `uv run pytest -q` passing and (2) rendering the export and looking at it.
Before writing geometry, read the `build123d` skill. NOT CadQuery.

One folder per project, holding its plan doc, its `cad/` sources and its
exported output. A design is one module per part or piece in that `cad/`:
parameters as constants at the top, `build() -> Design`, run from the project
folder with `uv run python cad/<name>.py`. Its tests sit in `cad/tests/`, one
file per design. New reusable geometry belongs in `cadkit`, with a test, not
here.

Dimension changes go into the plan doc first, then the model.

Skills: `build123d` (geometry), `shop-drawings` (woodworking output),
`printability` (FDM), `cad-iterate` (the test → export → diff → look loop).
