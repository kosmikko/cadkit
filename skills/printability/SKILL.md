---
name: printability
description: Design functional FDM 3D-printed parts with cadkit.print — print orientation, overhang and support checks, fit clearances for press/sliding/free fits, build-volume fit, elephant-foot compensation, and the optional OrcaSlicer time/filament stage. Use when modelling anything to be 3D printed, choosing a tolerance, or checking whether a part needs supports.
---

# Printability for FDM

Functional parts, printed without supports, that fit together on the first
try. Read the `build123d` skill first if you are writing geometry.

## The orientation rule

**Model every part in print orientation with the bed at z=0.** Not in
assembly position — in the position it will actually be printed in. Use
`drop_to_bed(part)` if construction left it elsewhere.

This is what makes the checks mean anything: `overhang_faces()` on a part
lying in its assembled pose tells you nothing about whether it prints.

```python
design.placed = {"box": body, "lid": lid}      # print orientation, bed at z=0
design.seated = {"box": body, "lid": seated}   # assembled, for the fit tests
```

A printed lid is modelled flat on the bed with its lip up, and *seated*
flipped lip-down onto the box. Interference tests run against `seated`;
printability tests run against `placed`.

## Clearances

```python
from cadkit.print import CLEARANCE_PRESS, CLEARANCE_FIT, CLEARANCE_FREE
```

| Constant | Per side | For |
|---|---|---|
| `CLEARANCE_PRESS` | 0.1 mm | press fit, needs force |
| `CLEARANCE_FIT` | 0.2 mm | snug sliding fit — lids, sleeves |
| `CLEARANCE_FREE` | 0.4 mm | loose fit, moving parts |

These are **starting values, not truths**. Print a tolerance test and tune per
printer and per material. Two things stay true across printers: **holes
shrink**, and **x/y needs more clearance than z**.

## The checks every printed design owes

```python
from cadkit.print import fits_bed, material_grams, overhang_faces

def test_needs_no_support(design):
    for name, part in design.placed.items():
        assert part.bounding_box().min.Z == pytest.approx(0), name   # on the bed
        assert overhang_faces(part) == [], f"{name} needs support"

def test_fits_bed(design):
    for name, part in design.placed.items():
        assert fits_bed(part), name
```

Plus the seated no-interference and engagement tests from the `build123d`
skill's `references/booleans.md`.

**Set `BED` in `cadkit/print/printability.py` to the actual printer** before
trusting `fits_bed`. It defaults to `(175, 180, 170)` — a Qidi Tech X-Smart 3.
`fits_bed` allows a 90° rotation on the bed.

### How overhang_faces judges

A face needs support when it points downward more steeply than the limit:
`normal.Z < -sin(max_overhang_deg)`. Two things follow:

- **A 45° chamfer sits exactly on the default 45° limit and passes.** Pass
  `max_overhang_deg` to match the real printer profile if yours is tighter.
- **Curved faces are judged by their centre normal** — good enough for
  functional parts, not for organic shapes.
- Only *horizontal* faces at bed level are exempted as bed contact. A tilted
  face touching the bed still gets flagged, which is correct: slicers support
  most of its area.

## Designing for no supports

- **Chamfer at 45° instead of leaving a shallow overhang.** This is the whole
  trick, and it is why the enclosure's lid and box both print flat.
- Add `FOOT_CHAMFER = 0.3` on bed-contact edges to compensate for elephant
  foot — the first-layer squish that makes the base a fraction oversize.
- Prefer a shape that needs no supports over one that prints "fine with
  supports": support scarring lands on exactly the mating surfaces whose
  tolerance you just tuned.

## Material and slicing

`material_grams(part)` is a rough estimate — `infill=1.0` gives the solid
upper bound; real prints with walls and 15–40 % infill land well below it.

`slice_stl(stl, outdir)` runs OrcaSlicer headlessly and parses time and
filament from the G-code comments. It returns `None` when no slicer is
installed, and the export prints stats when available and stays quiet
otherwise. Install with `brew install --cask orcaslicer`.

## Import note

Import as `cadkit.print` or `from cadkit.print import ...`. Never
`from cadkit import print` — that shadows the builtin in the importing module.
