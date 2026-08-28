# my-cad-project

Parametric designs in build123d, verified with pytest, exported headlessly.
The stack lives in [cadkit](https://github.com/kosmikko/cadkit).

One folder per thing you are building. The folder holds its plan doc, its CAD
source under `cad/`, and its output: the shop PDF and the cut list at the
root, sheets in `svg/`, the model in `step/`.

```
example/
  example-plan.md         the source of truth for dimensions
  example_cutlist.csv     take this to the yard
  example_summary.json    what the model actually measures
  cad/example.py
  cad/tests/test_example.py
  svg/                    dimensioned part sheets
  step/example.step
  .golden/                visual-diff baseline (gitignored)
```

```bash
uv sync
uv run pytest -q                       # every project's geometry tests

cd example
uv run python cad/example.py           # export into this folder
uv run python cad/example.py --only top --skip-pdf   # scoped
uv run cadkit diff                     # what changed since the last snapshot
uv run cadkit probe example "placed['top'].volume"   # run from cad/
```

Rename the project in `pyproject.toml`, then delete this paragraph and the
`[tool.uv.sources]` block if you are not developing cadkit alongside it.
