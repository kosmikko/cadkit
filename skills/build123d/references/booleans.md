# Boolean ops as verification

Geometry questions have exact answers. Ask them in a test rather than
eyeballing a render — this is what makes code-CAD converge.

## The three checks every design owes

```python
def test_overall_envelope(design):
    bb = Compound(children=list(design.placed.values())).bounding_box()
    assert bb.size.X == pytest.approx(WIDTH, abs=0.01)

def test_no_part_interference(design):
    """No two placed parts may occupy the same space."""
    for (na, a), (nb, b) in itertools.combinations(design.placed.items(), 2):
        assert (a & b).volume == pytest.approx(0, abs=1e-6), f"{na} intersects {nb}"

def test_joint_engages(design):
    """Intersect the part with the MATING PART'S STOCK ENVELOPE, not the cut part."""
    stock = block(T, DEPTH, HEIGHT)          # the side before its dadoes were cut
    assert (shelf & stock).volume == pytest.approx(expected, rel=0.01)
```

The engagement test is the one that catches "the tenon is 2 mm short": it
intersects against the *uncut* envelope, so it measures how deep the part
actually reaches, which a no-interference test can never tell you.

For 3D prints, run the interference tests against `design.seated` — the
assembled positions — because `design.placed` holds parts in print
orientation, laid out flat on the bed, where nothing touches anything.

## Computing the number you expect

The trap is always in the expected value, not the measurement.

- **A dado that reaches a panel edge is an open rabbet** and removes *less*
  stock than a through dado. Clamp the cutter span to the panel:
  `cut = min(z + T + c/2, HEIGHT) - max(z - c/2, 0)`.
- **Engagement loses half the clearance at each end**, so a nominal
  `DADO_DEPTH` engages `DADO_DEPTH - CLEARANCE / 2`.
- **Fillets and chamfers remove a sliver.** Use `rel=0.01` rather than
  chasing the exact volume of a rounded corner, or compute it:
  a rounded rectangle's area is `l * w - (4 - pi) * r**2`.

## When the volume test is not enough

A volume test proves size, never orientation or identity. Two mirrored parts
have identical volumes. That is why the workflow rule requires rendering the
export and looking at it as well — a mirrored label frame passed every test
in the suite and was caught only by the vision check.
