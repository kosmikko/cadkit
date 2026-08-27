import builtins
import csv

import pytest

from cadkit.wood import Part, block, markdown, rows, write_csv


def test_explicit_cut_dims_override_rotated_shape_bbox():
    part = Part("brace", block(9, 8, 7), cut_dims=(913.666, 98, 48))
    assert part.dims() == (913.7, 98, 48)
    row = rows([part])[0]
    assert (row["length_mm"], row["width_mm"], row["thickness_mm"]) == (
        913.7,
        98,
        48,
    )


def test_part_without_cut_dims_keeps_bbox_behavior():
    assert Part("panel", block(18, 250, 800)).dims() == (800, 250, 18)


def test_part_key_is_stable_metadata_not_exported_in_rows():
    keyed = Part("kattovaso", block(1, 2, 3), key="rafter")

    assert keyed.key == "rafter"
    assert "key" not in rows([keyed])[0]
    assert Part("legacy", block(1, 2, 3)).key is None


def test_write_csv_uses_utf8_and_round_trips_finnish_text(tmp_path, monkeypatch):
    destination = tmp_path / "cutlist.csv"
    real_open = builtins.open
    calls = []

    def recording_open(*args, **kwargs):
        calls.append((args, kwargs))
        return real_open(*args, **kwargs)

    monkeypatch.setattr(builtins, "open", recording_open)
    write_csv([Part("kattovason välikappale", block(1, 2, 3))], destination)

    assert calls == [((destination, "w"), {"newline": "", "encoding": "utf-8"})]
    with destination.open(encoding="utf-8", newline="") as output:
        assert list(csv.DictReader(output))[0]["part"] == "kattovason välikappale"


def test_write_csv_uses_lf_line_endings(tmp_path):
    destination = tmp_path / "cutlist.csv"

    write_csv([Part("osa", block(1, 2, 3))], destination)

    output = destination.read_bytes()
    assert b"\r\n" not in output
    assert output.count(b"\n") == 2


def test_markdown_default_output_is_unchanged():
    assert markdown([Part("osa", block(1, 2, 3))]) == (
        "| part | qty | L (mm) | W (mm) | T (mm) | material | note |\n"
        "|---|---|---|---|---|---|---|\n"
        "| osa | 1 | 3.0 | 2.0 | 1.0 | plywood |  |"
    )


def test_markdown_accepts_seven_localized_headers():
    headers = (
        "osa",
        "kpl",
        "P (mm)",
        "L (mm)",
        "S (mm)",
        "materiaali",
        "huomautus",
    )

    assert markdown([Part("osa", block(1, 2, 3))], headers=headers) == (
        "| osa | kpl | P (mm) | L (mm) | S (mm) | materiaali | huomautus |\n"
        "|---|---|---|---|---|---|---|\n"
        "| osa | 1 | 3.0 | 2.0 | 1.0 | plywood |  |"
    )


def test_markdown_rejects_header_count_other_than_seven():
    with pytest.raises(ValueError, match="exactly 7"):
        markdown([Part("osa", block(1, 2, 3))], headers=("osa",))
