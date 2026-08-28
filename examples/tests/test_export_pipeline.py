"""SETUP.md section 3, as an assertion instead of a manual checklist.

Both reference designs must export end to end from a clean directory. This is
the test that catches a broken install, a renamed helper, or an artifact that
silently stopped being written — the things a human used to catch by running
the commands in the README and squinting at `ls export/`.
"""

import json

import pytest

from cadkit.core import export_all
from examples import bookshelf, enclosure


@pytest.mark.slow
def test_bookshelf_exports_everything(tmp_path):
    written = export_all(bookshelf.build(), tmp_path, quiet=True)
    assert set(written) == {
        "step/bookshelf.step",
        "bookshelf_cutlist.csv",
        "svg/bookshelf_side.svg",
        "svg/bookshelf_shelf.svg",
        "svg/bookshelf_exploded.svg",
        "bookshelf_summary.json",
    }
    for name in written:
        assert (tmp_path / name).stat().st_size > 0, name
    assert (tmp_path / "svg" / "bookshelf_exploded.svg").read_text().startswith("<svg")

    summary = json.loads((tmp_path / "bookshelf_summary.json").read_text())
    assert summary["units"] == "mm"
    assert summary["placed"]["side_left"]["size"] == [
        bookshelf.T, bookshelf.DEPTH, bookshelf.HEIGHT
    ]
    assert {row["part"] for row in summary["cutlist"]} == {"side", "shelf"}


@pytest.mark.slow
def test_enclosure_exports_everything(tmp_path):
    written = export_all(enclosure.build(), tmp_path, quiet=True)
    # the STL is the headline output of a printed part, so it sits at the root;
    # the iso preview is a sheet and goes to svg/
    assert set(written) == {
        "enclosure_box.stl",
        "svg/enclosure_box.svg",
        "enclosure_lid.stl",
        "svg/enclosure_lid.svg",
        "enclosure_summary.json",
    }
    assert (tmp_path / "enclosure_box.stl").stat().st_size > 1000
    assert (tmp_path / "svg" / "enclosure_lid.svg").read_text().startswith("<svg")

    summary = json.loads((tmp_path / "enclosure_summary.json").read_text())
    assert summary["seated"]["lid"]["bbox_min"][2] == pytest.approx(
        enclosure.OUTER_H - enclosure.LIP_H
    )
    assert summary["meta"]["box"]["fits_bed"] is True


@pytest.mark.slow
def test_only_and_skip_scope_the_export(tmp_path):
    """--only and --skip exist to scope the render-and-inspect loop, not the build."""
    design = bookshelf.build()
    written = export_all(design, tmp_path, only=("side",), quiet=True)
    assert written == ["svg/bookshelf_side.svg", "bookshelf_summary.json"]

    out = tmp_path / "no-step"
    written = export_all(design, out, skip=("step", "csv"), quiet=True)
    assert not any(n.endswith((".step", ".csv")) for n in written)
    # the summary is derived from the model, so a scoped export still answers
    # "what are the dimensions now?"
    assert "bookshelf_summary.json" in written
