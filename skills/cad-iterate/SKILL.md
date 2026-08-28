---
name: cad-iterate
description: The code-CAD iteration loop — scoped tests, scoped export with --only/--skip, golden-PNG visual diff to find what actually changed, probe and summary.json instead of throwaway python -c one-liners, and the final full inspection. Use when iterating on an existing design, when an export is slow or noisy, or when deciding which rendered pages still need looking at.
---

# The iteration loop

Compute is not the bottleneck. An export is 2–4 seconds and a test suite is
seconds to a minute; what costs time and tokens is everything around them —
re-reading big files, re-rendering everything, and re-inspecting pages that
did not change.

The loop, per edit:

Run it from the project folder — the one holding the plan doc, `cad/` and
the exported output:

```bash
uv run pytest -q cad/tests/test_<design>.py       # 1. scoped tests
uv run python cad/<name>.py --only <part>         # 2. scoped export
uv run cadkit diff                                # 3. what actually changed
# 4. look at ONLY the PNGs the diff names
```

Then once, before claiming done: full suite, full export, look at everything,
`uv run cadkit snapshot`.

## 1. Ask the model, don't grep the source

Every export writes `<name>_summary.json` at the project root: per-part
bboxes, sizes,
centres, volumes, the cut list, and the artifact inventory. Read that to
answer "how long is rafter_3 now?" instead of rereading a 3000-line module.

For anything the summary does not cover, use `probe` rather than a
quoting-fragile `python -c` one-liner:

```bash
uv run cadkit probe shelter "placed['rafter_1'].bounding_box().size.Z"   # from cad/
uv run cadkit probe shelter "(placed['a'] & placed['b']).volume"
```

`placed`, `parts`, `seated`, `design` and the whole build123d namespace are in
scope. The summary is written even when `--only` skipped every artifact,
because it comes from the model rather than the files.

## 2. Scope the export

```bash
uv run python cad/<name>.py --only side      # just the parts that matter
uv run python cad/<name>.py --skip-pdf       # PDFs are the slow artifact
uv run python cad/<name>.py --skip-step --skip-csv
```

The runner prints what it skipped and why, so a scoped export never quietly
looks like a full one. `--skip-<kind>` exists for every artifact kind.

The point is not the seconds saved on the export — it is scoping the
**render-and-inspect** work downstream, which is where the tokens go.

## 3. Diff-scoped inspection — don't re-look at what didn't change

`cadkit diff` keeps golden PNG renders of every `.svg` and `.pdf` in the
project folder — `svg/` included — and reports what an edit actually altered.
Run from inside the project folder:

```bash
uv run cadkit snapshot   # accept the current output as the baseline
uv run cadkit diff       # report what changed since the baseline
```

It skips unchanged artifacts by content hash without rendering them, and
writes the changed renders plus red-overlay diffs to `.golden/_diff/`, printing
their paths. **Read only those.** Optional name-substring filters scope either
command (`cadkit diff shelter`).

`.golden/` is per-machine state and is gitignored. If `diff` reports
everything as NEW, snapshot a known-good state first.

## 4. Looking at the render is not optional

The full every-page inspection is still owed **once**, on the final result,
before claiming done. Run `cadkit snapshot` after it so the next change starts
from an accepted baseline.

Render on macOS:

```bash
qlmanage -t -s 1000 -o <scratch> svg/thing.svg   # then read the PNG
```

**qlmanage square-crops non-square sheets** — for tall or wide sheets, split
the SVG viewBox into halves first. On Linux use `rsvg-convert`. For PDFs use
PyMuPDF, which renders every page; Quick Look only renders the first.

## Why both halves of the rule exist

Both failure modes have actually happened in this codebase:

- A **volume test** caught wrong geometry assumptions that looked fine.
- Only the **vision check** caught a mirrored label frame that passed every
  test in the suite.

A test proves size; it cannot prove orientation or identity. Neither check
substitutes for the other.

## Converting eyeball checks into assertions

Every bug class the vision loop has caught can become an SVG-level test —
text present, leader endpoints inside the part bbox, sheet aspect within
bounds. Each conversion permanently removes a vision read from the loop.
Prefer writing one over re-looking at the same page a third time.

## Per-design notes

A design with real history keeps it in `cad/NOTES.md` next to the
module — artifact inventory, decisions worth keeping, gotchas, and its
render-and-inspect checklist. **Read that file in full before editing the
design or its tests**, and record new design-specific lessons there rather
than in the project briefing.
