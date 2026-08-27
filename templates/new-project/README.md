# my-cad-project

Parametric designs in build123d, verified with pytest, exported headlessly.
The stack lives in [cadkit](https://github.com/kosmikko/cadkit).

```bash
uv sync
uv run pytest -q                        # geometry verification
uv run python -m designs.<name>         # export everything to export/
uv run python -m designs.<name> --only <part> --skip-pdf   # scoped
uv run cadkit diff                      # what changed since the last snapshot
uv run cadkit probe designs.<name> "placed['part'].volume"
```

Rename the project in `pyproject.toml`, then delete this paragraph and the
`[tool.uv.sources]` block if you are not developing cadkit alongside it.
