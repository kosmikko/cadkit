"""Cut list generation from part solids.

Panel dims are taken from the part's bounding box, sorted descending:
length x width x thickness. Joinery cuts (dadoes, rabbets) don't change
the blank size, so bbox is the right source for panel stock.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass

DEFAULT_MARKDOWN_HEADERS = (
    "part",
    "qty",
    "L (mm)",
    "W (mm)",
    "T (mm)",
    "material",
    "note",
)


@dataclass
class Part:
    name: str
    shape: object  # build123d solid
    qty: int = 1
    material: str = "plywood"
    note: str = ""
    cut_dims: tuple[float, float, float] | None = None
    key: str | None = None

    def dims(self) -> tuple[float, float, float]:
        if self.cut_dims is not None:
            return tuple(round(v, 1) for v in self.cut_dims)
        bb = self.shape.bounding_box()
        d = sorted((bb.size.X, bb.size.Y, bb.size.Z), reverse=True)
        return tuple(round(v, 1) for v in d)


def rows(parts: list[Part]) -> list[dict]:
    out = []
    for p in parts:
        length, width, thickness = p.dims()
        out.append(
            {
                "part": p.name,
                "qty": p.qty,
                "length_mm": length,
                "width_mm": width,
                "thickness_mm": thickness,
                "material": p.material,
                "note": p.note,
            }
        )
    return out


def write_csv(parts: list[Part], path):
    rs = rows(parts)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=list(rs[0].keys()), lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rs)


def markdown(
    parts: list[Part], headers: tuple[str, ...] = DEFAULT_MARKDOWN_HEADERS
) -> str:
    if len(headers) != 7:
        raise ValueError("markdown headers must contain exactly 7 values")
    rs = rows(parts)
    lines = [
        f"| {' | '.join(headers)} |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rs:
        lines.append(
            f"| {r['part']} | {r['qty']} | {r['length_mm']} | {r['width_mm']} "
            f"| {r['thickness_mm']} | {r['material']} | {r['note']} |"
        )
    return "\n".join(lines)
