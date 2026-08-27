---
name: build123d
description: Model 3D geometry in build123d algebra mode — the cheatsheet, the selector idioms, and the empirically verified gotchas. THIS IS NOT CadQuery. Use whenever writing or editing build123d code, CAD parts, parametric models, or any .py file that imports build123d, and when an agent reaches for Workplane, chained calls, or string selectors.
---

# build123d — THIS IS NOT CadQuery

**No `Workplane`. No chained calls. No string selectors.** This is the single
most expensive failure mode in code-CAD: an agent pattern-matches to CadQuery
(or to a half-remembered tutorial) and writes
`Workplane("XY").box(1,2,3).faces(">Z").hole(4)`. None of that exists here.
build123d algebra mode is plain Python — objects, operators, and list
comprehensions over real selector objects.

Units are mm throughout.

## The cheatsheet

```python
from build123d import *          # algebra mode, no builders needed
p = Box(800, 250, 18)            # centered at origin
p = Pos(10, 0, 5) * Box(...)     # position (also Rot(x,y,z) for rotation)
p -= cutter                      # boolean subtract; + is union, & is intersect
                                 # (NOT | — algebra mode does not implement it)
p.volume, p.bounding_box()       # bb.min/.max/.size/.center() are Vectors
mirror(p, about=Plane.YZ.offset(400))
Compound(children=[a, b])        # group solids; export_step(comp, "f.step")
export_stl(p, "f.stl")           # mesh export for printing
e @ 0.5                          # point on edge/wire at parameter t
p.faces().filter_by(Axis.Z).sort_by(Axis.Z)[-1]   # selectors are Python
face.normal_at()                 # face normal (center) — printability checks
fillet(p.edges().filter_by(Axis.Z), radius=3)     # returns a NEW solid
chamfer(p.edges().group_by(Axis.Z)[0], length=0.4)
```

Selectors return list-likes you filter, sort and index with ordinary Python:
`filter_by(Axis.Z)`, `group_by(Axis.Z)`, `sort_by(Axis.X)`, `[-1]`, `[0]`.
There is no query mini-language to guess at — if you are writing a string to
select geometry, you are writing CadQuery.

## The four gotchas that have actually cost time

1. **Union is `+`, not `|`.** Algebra mode does not implement `|` at all — it
   raises TypeError. Cost an iteration once.
2. **Put the projection camera far away** (~1e5 mm). `project_to_viewport` is
   perspective, not orthographic; a near camera distorts scale (18 mm → 18.04
   at 0.5 m). See `references/hlr.md`.
3. **HLR output is self-centered per call.** Two separate projections do NOT
   share a 2D frame. See `references/hlr.md`.
4. **fillet/chamfer throw OCCT kernel errors** on complex edge combinations.
   Apply them late, on explicitly filtered edge sets. See
   `references/fillets.md`.

## Boolean ops are free verification

This is the habit that separates converging from flailing. Geometry questions
have exact answers; ask them in a test instead of eyeballing a render:

```python
assert (a & b).volume == pytest.approx(0)          # parts do not collide
assert (part & mating_stock).volume == expected    # the joint actually engages
```

`references/booleans.md` has the patterns — envelope, pairwise
no-interference, engagement volume — and the traps in computing the expected
number (an open-ended dado removes less stock than a through dado).

## References

- `references/hlr.md` — hidden-line removal, view frames, camera distance,
  mapping 3D points into a projected view
- `references/booleans.md` — verification patterns and how to compute the
  volume you expect
- `references/fillets.md` — where fillet/chamfer fail and what to do instead

## The library

Geometry helpers that are already written and tested live in `cadkit`:
`cadkit.wood` (block, dado, cut lists, nesting), `cadkit.print`
(printability, bed fit, clearances), `cadkit.draw` (projection to SVG).
Compose those rather than wrangling raw geometry — and put genuinely new
reusable geometry back into them, with a test.
