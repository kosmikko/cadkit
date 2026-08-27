"""cadkit.verify — the golden-PNG diff that scopes visual inspection."""

from cadkit import verify as visual_diff

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="40mm" '
    'viewBox="0 0 60 40">{extra}'
    '<rect x="{x}" y="10" width="20" height="20" fill="none" stroke="#111"/></svg>'
)


def write_svg(export, x=10, name="part.svg", extra=""):
    export.mkdir(exist_ok=True)
    (export / name).write_text(SVG.format(x=x, extra=extra))


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
