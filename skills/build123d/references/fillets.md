# fillet and chamfer

Both return a **new solid**; neither mutates in place.

```python
p = fillet(p.edges().filter_by(Axis.Z), radius=3)
p = chamfer(p.edges().group_by(Axis.Z)[0], length=0.4)
```

## They fail on complex edge sets

OCCT throws kernel errors when asked to round a set of edges whose blends
would collide or run off the end of their faces. The failure is often a bare
exception with no useful location.

What works:

- **Apply them late**, after the booleans, on the finished shape.
- **Filter explicitly.** `p.edges()` on a part with dozens of edges is a
  request for trouble; `p.edges().filter_by(Axis.Z)` (the vertical edges) or
  `p.edges().group_by(Axis.Z)[0]` (the bottom ring) is a request the kernel
  can satisfy.
- **Shrink the radius.** A fillet radius approaching the local feature size
  fails. An inner fillet following an outer one wants `R - WALL`, and that
  can go negative — clamp it: `max(CORNER_R - WALL - CLEARANCE, 0.5)`.
- **Split the operation.** Two `fillet` calls on two edge groups often
  succeed where one call on their union fails.

## 45° is the printing hinge

For FDM, a 45° chamfer sits exactly on the default overhang limit and passes
`overhang_faces()`. Chamfering at 45° instead of leaving a shallow overhang
is the standard way to make a part support-free — see the `printability`
skill.

Bed-contact edges get a small chamfer (`FOOT_CHAMFER = 0.3`) to compensate
for elephant foot.
