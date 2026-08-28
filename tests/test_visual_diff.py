"""cadkit.verify — the golden-PNG diff that scopes visual inspection."""

from cadkit import verify as visual_diff

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="40mm" '
    'viewBox="0 0 60 40">{extra}'
    '<rect x="{x}" y="10" width="20" height="20" fill="none" stroke="#111"/></svg>'
)


def write_svg(export, x=10, name="part.svg", extra=""):
    path = export / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SVG.format(x=x, extra=extra))


def test_snapshot_then_diff_is_clean(tmp_path):
    export, golden = tmp_path / "export", tmp_path / ".golden"
    write_svg(export)
    visual_diff.snapshot(export, golden, [])
    assert visual_diff.diff(export, golden, []) == ["1 artifact(s) unchanged"]


def test_moved_geometry_is_flagged_with_a_render_and_an_overlay(tmp_path):
    export, golden = tmp_path / "export", tmp_path / ".golden"
    write_svg(export, x=10)
    visual_diff.snapshot(export, golden, [])
    write_svg(export, x=30)
    report = visual_diff.diff(export, golden, [])
    assert any(r.startswith("CHANGED part.svg: page 1 (") for r in report)
    out = golden / "_diff" / "part.svg"
    assert (out / "page-1.png").exists() and (out / "page-1.diff.png").exists()


def test_byte_change_with_identical_render_is_not_a_visual_change(tmp_path):
    export, golden = tmp_path / "export", tmp_path / ".golden"
    write_svg(export)
    visual_diff.snapshot(export, golden, [])
    write_svg(export, extra="<!-- reordered exporter output -->")
    report = visual_diff.diff(export, golden, [])
    assert "unchanged render (source bytes differ): part.svg" in report
    assert not any(r.startswith("CHANGED") for r in report)


def test_new_and_missing_artifacts_are_reported(tmp_path):
    export, golden = tmp_path / "export", tmp_path / ".golden"
    write_svg(export, name="old.svg")
    visual_diff.snapshot(export, golden, [])
    (export / "old.svg").unlink()
    write_svg(export, name="new.svg")
    report = "\n".join(visual_diff.diff(export, golden, []))
    assert "NEW (no baseline" in report and "new.svg" in report
    assert "MISSING (baseline exists, not exported): old.svg" in report


def test_name_filters_scope_both_commands(tmp_path):
    export, golden = tmp_path / "export", tmp_path / ".golden"
    write_svg(export, name="desk.svg")
    write_svg(export, name="rack.svg")
    visual_diff.snapshot(export, golden, [])
    write_svg(export, name="desk.svg", x=30)
    write_svg(export, name="rack.svg", x=30)
    report = "\n".join(visual_diff.diff(export, golden, ["desk"]))
    assert "desk.svg" in report and "rack.svg" not in report


def test_sheets_in_subfolders_are_found_and_diffed(tmp_path):
    """The project folder is the export dir now, and its sheets live in svg/."""
    export, golden = tmp_path / "project", tmp_path / "project" / ".golden"
    write_svg(export, name="svg/part.svg")
    write_svg(export, name="package.svg")  # a root-level artifact still counts
    assert [p.name for p in visual_diff.artifacts(export, [])] == [
        "package.svg", "part.svg",
    ]

    visual_diff.snapshot(export, golden, [])
    assert visual_diff.diff(export, golden, []) == ["2 artifact(s) unchanged"]

    write_svg(export, name="svg/part.svg", x=30)
    report = visual_diff.diff(export, golden, [])
    assert any(r.startswith("CHANGED part.svg: page 1 (") for r in report)
    assert "1 artifact(s) unchanged" in report


def test_the_baseline_does_not_diff_itself(tmp_path):
    """.golden/ holds PNGs, but _diff/ holds rendered SVG copies — skip dot-dirs."""
    export, golden = tmp_path / "project", tmp_path / "project" / ".golden"
    write_svg(export, name="svg/part.svg")
    visual_diff.snapshot(export, golden, [])
    # a stray SVG under .golden/ must not be picked up as an artifact
    write_svg(golden, name="stray.svg")
    assert [p.name for p in visual_diff.artifacts(export, [])] == ["part.svg"]
    assert visual_diff.diff(export, golden, []) == ["1 artifact(s) unchanged"]
