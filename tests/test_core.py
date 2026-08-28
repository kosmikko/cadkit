"""cadkit.core — the Design declaration and the export runner."""

import json

import pytest
from build123d import Box, Pos

from cadkit.core import LAYOUT, Artifact, Design, export_all, probe


def _cube(size=10.0, at=(0, 0, 0)):
    return Pos(*at) * Box(size, size, size)


def test_unknown_artifact_kind_is_rejected():
    with pytest.raises(ValueError, match="unknown artifact kind"):
        Artifact("x", "dxf", "x.dxf", lambda p: None)


def test_runner_writes_declared_artifacts(tmp_path):
    design = Design("widget")
    design.add("a", "md", "a.md", lambda p: p.write_text("a"))
    design.add("b", "md", "b.md", lambda p: p.write_text("b"))
    written = export_all(design, tmp_path, summary=False, quiet=True)
    assert written == ["a.md", "b.md"]
    assert (tmp_path / "a.md").read_text() == "a"


def test_only_filters_by_name_or_filename(tmp_path):
    design = Design("widget")
    design.add("side", "md", "widget_side.md", lambda p: p.write_text("s"))
    design.add("shelf", "md", "widget_shelf.md", lambda p: p.write_text("h"))
    written = export_all(design, tmp_path, only=("side",), summary=False, quiet=True)
    assert written == ["widget_side.md"]
    assert not (tmp_path / "widget_shelf.md").exists()


def test_skip_drops_a_whole_kind(tmp_path):
    design = Design("widget")
    design.add("sheet", "svg", "widget.svg", lambda p: p.write_text("<svg/>"))
    design.pdf(lambda p: p.write_bytes(b"%PDF"), name="package")
    written = export_all(design, tmp_path, skip=("pdf",), summary=False, quiet=True)
    assert written == ["svg/widget.svg"]


def test_summary_records_geometry(tmp_path):
    design = Design("widget")
    design.placed = {"cube": _cube(10, at=(5, 5, 5))}
    export_all(design, tmp_path, quiet=True)
    summary = json.loads((tmp_path / "widget_summary.json").read_text())
    cube = summary["placed"]["cube"]
    assert cube["size"] == [10.0, 10.0, 10.0]
    assert cube["center"] == [5.0, 5.0, 5.0]
    assert cube["volume"] == pytest.approx(1000.0)
    assert summary["units"] == "mm"


def test_summary_lists_artifacts_even_when_they_were_skipped(tmp_path):
    design = Design("widget")
    design.add("sheet", "svg", "widget.svg", lambda p: p.write_text("<svg/>"))
    export_all(design, tmp_path, skip=("svg",), quiet=True)
    summary = json.loads((tmp_path / "widget_summary.json").read_text())
    assert summary["artifacts"] == [
        {"name": "sheet", "kind": "svg", "file": "svg/widget.svg"}
    ]
    assert not (tmp_path / "svg" / "widget.svg").exists()


def test_layout_sorts_artifacts_into_subfolders(tmp_path):
    """A project folder keeps its headline output at the root, sheets in svg/."""
    design = Design("widget")
    design.add("sheet", "svg", "widget_side.svg", lambda p: p.write_text("<svg/>"))
    design.add("model", "step", "widget.step", lambda p: p.write_text("ISO-10303-21;"))
    design.add("list", "csv", "widget_cutlist.csv", lambda p: p.write_text("part\n"))
    written = export_all(design, tmp_path, summary=False, quiet=True)

    assert written == ["svg/widget_side.svg", "step/widget.step", "widget_cutlist.csv"]
    # the runner, not the caller, creates the subfolders
    assert (tmp_path / "svg" / "widget_side.svg").read_text() == "<svg/>"
    assert (tmp_path / "step" / "widget.step").exists()
    assert (tmp_path / "widget_cutlist.csv").exists()


def test_layout_applies_to_the_convenience_methods_too(tmp_path):
    """`iso`/`drawing`/`exploded` build a filename and hand it to add(), which prefixes."""
    design = Design("widget")
    design.placed = {"cube": _cube()}
    design.iso("cube", design.placed["cube"])
    export_all(design, tmp_path, summary=False, quiet=True)
    assert (tmp_path / "svg" / "widget_cube.svg").exists()


def test_layout_is_overridable_per_design(tmp_path):
    """A design that wants everything flat says so; an empty map means no subfolders."""
    design = Design("widget", layout={})
    design.add("sheet", "svg", "widget.svg", lambda p: p.write_text("<svg/>"))
    written = export_all(design, tmp_path, summary=False, quiet=True)
    assert written == ["widget.svg"]
    assert (tmp_path / "widget.svg").exists()

    other = Design("widget", layout={"svg": "sheets"})
    other.add("sheet", "svg", "widget.svg", lambda p: p.write_text("<svg/>"))
    export_all(other, tmp_path, summary=False, quiet=True)
    assert (tmp_path / "sheets" / "widget.svg").exists()

    # the default map is copied per design, not shared
    assert Design("a").layout == LAYOUT and Design("a").layout is not LAYOUT


def test_summary_stays_at_the_root(tmp_path):
    """The summary is the design's answer sheet — it belongs beside the plan doc."""
    design = Design("widget")
    design.add("sheet", "svg", "widget.svg", lambda p: p.write_text("<svg/>"))
    written = export_all(design, tmp_path, quiet=True)
    assert written[-1] == "widget_summary.json"
    assert (tmp_path / "widget_summary.json").exists()


def test_probe_evaluates_against_the_design():
    design = Design("widget")
    design.placed = {"a": _cube(10), "b": _cube(10, at=(100, 0, 0))}
    assert probe(design, "placed['a'].volume") == pytest.approx(1000.0)
    assert probe(design, "(placed['a'] & placed['b']).volume") == pytest.approx(0.0)
    # the build123d namespace is in scope, so a probe can build its own geometry
    assert probe(design, "Box(2, 2, 2).volume") == pytest.approx(8.0)


def test_cutlist_without_parts_is_an_error(tmp_path):
    design = Design("widget")
    design.cutlist()
    with pytest.raises(ValueError, match="parts is empty"):
        export_all(design, tmp_path, quiet=True)
