"""Guillotine strip nesting: parts onto sheet goods, kerf-aware, few cuts.

A layout is only buildable on a saw that cuts edge to edge if it is a
*guillotine* layout — every cut runs the full width of the piece it divides.
The cheapest guillotine layout to cut is a strip layout: rip the panel into
full-length strips, then crosscut parts off each strip. The rips are the only
cuts that have to handle a whole panel, and there is one fewer of them than
there are strips.

The packer is deliberately not a search. It does what a person does at the saw:
find the dimension the most parts share, rip strips that wide, fill them, and
repeat with what is left. On a casework parts list — which is full of repeated
widths, because the carcasses are all the same depth — that beats a generic bin
packer and, more to the point, it produces a layout somebody can follow.

Axes: a panel is `length` along x and `width` across y. A strip spans the full
length at some y; parts sit along it at increasing x.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TOL = 1e-6
#: Two dimensions count as "the same width" within this, in mm. Cut sizes are
#: quoted to 0.1, so anything tighter would split 493.8 from itself.
WIDTH_TOL = 0.05


@dataclass(frozen=True)
class Piece:
    """One part to cut. `length` and `width` are the blank, either way round."""

    name: str
    length: float
    width: float

    @property
    def area(self) -> float:
        return self.length * self.width

    def orientations(self) -> tuple[tuple[float, float], ...]:
        """(along the strip, across it) — both ways unless it is square."""
        if abs(self.length - self.width) < TOL:
            return ((self.length, self.width),)
        return ((self.length, self.width), (self.width, self.length))


@dataclass(frozen=True)
class Placement:
    name: str
    x: float  # along the panel, from its min corner
    y: float  # across the panel
    length: float  # as placed, along the panel
    width: float  # as placed, across it

    @property
    def area(self) -> float:
        return self.length * self.width


@dataclass
class Strip:
    """One rip: full panel length, `width` across, parts crosscut off it."""

    width: float
    placements: list[Placement] = field(default_factory=list)
    used: float = 0.0

    @property
    def area(self) -> float:
        return sum(p.area for p in self.placements)


@dataclass
class Panel:
    strips: list[Strip] = field(default_factory=list)

    @property
    def placements(self) -> list[Placement]:
        return [p for strip in self.strips for p in strip.placements]

    @property
    def used_width(self) -> float:
        return sum(s.width for s in self.strips)


@dataclass
class Nesting:
    panels: list[Panel]
    panel_length: float
    panel_width: float
    kerf: float

    @property
    def placements(self) -> list[Placement]:
        return [p for panel in self.panels for p in panel.placements]

    @property
    def part_area(self) -> float:
        return sum(p.area for p in self.placements)

    @property
    def panel_area(self) -> float:
        return len(self.panels) * self.panel_length * self.panel_width

    @property
    def utilisation(self) -> float:
        return self.part_area / self.panel_area

    @property
    def cut_count(self) -> int:
        """Rips plus crosscuts.

        One fewer rip than there are strips in a panel, and one crosscut to
        free each part — the last part on a strip needs one too unless it
        happens to end on the panel edge, which is not worth modelling.
        """
        total = 0
        for panel in self.panels:
            total += max(0, len(panel.strips) - 1)
            total += sum(len(s.placements) for s in panel.strips)
        return total


def _candidate_widths(pieces, panel_length, panel_width):
    """Every strip width worth trying: a dimension some piece could be ripped to.

    Ascending, because the caller keeps the *first* width that scores best and
    a narrower strip of the same content wastes less of the panel.
    """
    widths = set()
    for piece in pieces:
        for along, across in piece.orientations():
            if across <= panel_width + TOL and along <= panel_length + TOL:
                widths.add(round(across, 6))
    return sorted(widths)


def _members(pieces, width, panel_length):
    """(piece, length along the strip) for parts whose own width *is* this one.

    Exact match, not "fits inside". A strip only has to be as wide as its
    widest member, so admitting narrower parts would let one wide strip swallow
    the whole list and score best on area while wasting most of its width —
    which is exactly what a first cut of this did, on six panels instead of
    three. Grouping by a shared dimension is also what makes the plan
    followable: one rip setting, then crosscuts.
    """
    out = []
    for piece in pieces:
        for along, across in piece.orientations():
            if abs(across - width) <= WIDTH_TOL and along <= panel_length + TOL:
                out.append((piece, along))
                break
    return out


def _fill_strips(members, width, panel_length, kerf):
    """First-fit-decreasing by length: long parts first, into open strips."""
    strips: list[Strip] = []
    for piece, along in sorted(members, key=lambda m: (-m[1], m[0].name)):
        for strip in strips:
            start = strip.used + (kerf if strip.placements else 0.0)
            if start + along <= panel_length + TOL:
                strip.placements.append(
                    Placement(piece.name, start, 0.0, along, width)
                )
                strip.used = start + along
                break
        else:
            strip = Strip(width=width)
            strip.placements.append(Placement(piece.name, 0.0, 0.0, along, width))
            strip.used = along
            strips.append(strip)
    return strips


def _pack_strips(strips, panel_width, kerf):
    """First-fit-decreasing by width: strips into panels, widest first."""
    panels: list[Panel] = []
    for strip in sorted(strips, key=lambda s: (-s.width, -s.used)):
        for panel in panels:
            start = panel.used_width + (kerf * len(panel.strips))
            if start + strip.width <= panel_width + TOL:
                strip.placements = [
                    Placement(p.name, p.x, start, p.length, p.width)
                    for p in strip.placements
                ]
                panel.strips.append(strip)
                break
        else:
            panel = Panel()
            strip.placements = [
                Placement(p.name, p.x, 0.0, p.length, p.width)
                for p in strip.placements
            ]
            panel.strips.append(strip)
            panels.append(panel)
    return panels


def nest(pieces, *, panel_length, panel_width, kerf) -> Nesting:
    """Strip-nest `pieces` onto panels, widest shared dimension first.

    Raises if a piece cannot fit a panel in either orientation — a silent drop
    would be a cut list that does not add up.
    """
    for piece in pieces:
        if not any(
            along <= panel_length + TOL and across <= panel_width + TOL
            for along, across in piece.orientations()
        ):
            raise ValueError(
                f"{piece.name} ({piece.length:g} x {piece.width:g}) does not fit "
                f"a {panel_length:g} x {panel_width:g} panel"
            )

    remaining = list(pieces)
    strips: list[Strip] = []
    while remaining:
        # Take the width that sweeps up the most part area, and break ties on
        # the panel width it costs — strips x width. Both halves earn their
        # keep. Area first, because a group that strands a piece into a strip
        # of its own costs more than it saves: ripping the drawer sides to 644
        # is tighter for them but leaves the 500-wide bottom board alone, and
        # that is a whole extra panel. Width second, because three 550 x 400
        # boards cover the same area ripped to 400 (two strips, 800 of width)
        # as to 550 (one strip, 550), and only the second is the right answer.
        best = None
        for width in _candidate_widths(remaining, panel_length, panel_width):
            members = _members(remaining, width, panel_length)
            if not members:
                continue
            group = _fill_strips(members, width, panel_length, kerf)
            covered = sum(piece.area for piece, _ in members)
            key = (-covered, len(group) * width, width)
            if best is None or key < best[0]:
                best = (key, members, group)
        _key, members, group = best
        strips.extend(group)
        taken = {id(piece) for piece, _ in members}
        remaining = [p for p in remaining if id(p) not in taken]

    return Nesting(
        panels=_pack_strips(strips, panel_width, kerf),
        panel_length=panel_length,
        panel_width=panel_width,
        kerf=kerf,
    )
