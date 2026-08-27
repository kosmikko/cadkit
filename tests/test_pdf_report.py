import pymupdf
import pytest

from cadkit.draw import (
    A4_LANDSCAPE_MM,
    PdfReport,
    mm,
    rect_mm,
)

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" '
    'viewBox="0 0 20 10"><path d="M0 0 L20 10" stroke="black"/></svg>'
)


class FaultInjectingPage:
    def __init__(self, page, *, show_error=None, insert_error=None):
        self.page = page
        self.show_error = show_error
        self.insert_error = insert_error

    def show_pdf_page(self, *args, **kwargs):
        if self.show_error is not None:
            raise self.show_error
        return self.page.show_pdf_page(*args, **kwargs)

    def insert_text(self, *args, **kwargs):
        if self.insert_error is not None:
            raise self.insert_error
        return self.page.insert_text(*args, **kwargs)


def test_mm_and_a4_landscape_page_are_exact():
    assert mm(25.4) == pytest.approx(72)
    assert A4_LANDSCAPE_MM == (297.0, 210.0)

    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        size = (page.rect.width, page.rect.height)

    assert size == pytest.approx(
        tuple(mm(value) for value in A4_LANDSCAPE_MM)
    )


def test_pdf_font_round_trips_required_finnish_characters(tmp_path):
    text = "äöåÄÖÅ Ø × ° –"
    path = tmp_path / "font.pdf"

    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        report.textbox(page, rect_mm(10, 10, 100, 20), text)
        report.save(path)

    with pymupdf.open(path) as document:
        assert document[0].get_text().strip() == text


def test_save_is_deterministic_for_identical_reports(tmp_path):
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"

    for path in (first, second):
        with PdfReport() as report:
            report.add_a4_landscape_page()
            report.save(path)

    assert first.read_bytes() == second.read_bytes()


def test_textbox_raises_on_overflow():
    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        with pytest.raises(ValueError, match="text does not fit"):
            report.textbox(
                page,
                rect_mm(10, 10, 10, 2),
                "too much text",
                fontsize=12,
            )


def test_svg_placement_is_vector_and_emits_one_marker(tmp_path):
    svg = tmp_path / "part.svg"
    svg.write_text(SVG, encoding="utf-8")
    path = tmp_path / "vector.pdf"

    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        report.place_svg(page, rect_mm(10, 10, 100, 50), svg, "part.svg")
        report.save(path)

    with pymupdf.open(path) as document:
        page = document[0]
        marker = "DRAWING_ID:part.svg"
        assert page.get_text().count(marker) == 1
        assert page.get_images(full=True) == []
        assert len(page.get_xobjects()) > 0

        marker_spans = [
            span
            for span in page.get_texttrace()
            if "".join(chr(char[0]) for char in span["chars"]) == marker
        ]
        assert len(marker_spans) == 1
        assert marker_spans[0]["type"] == 3
        assert marker_spans[0]["size"] == pytest.approx(1)


def test_svg_placement_rejects_missing_file(tmp_path):
    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        with pytest.raises(ValueError, match="SVG missing"):
            report.place_svg(
                page,
                rect_mm(10, 10, 100, 50),
                tmp_path / "missing.svg",
                "part.svg",
            )


def test_svg_placement_rejects_empty_file(tmp_path):
    svg = tmp_path / "empty.svg"
    svg.write_bytes(b"")

    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        with pytest.raises(ValueError, match="SVG is empty"):
            report.place_svg(
                page, rect_mm(10, 10, 100, 50), svg, "part.svg"
            )


def test_svg_placement_wraps_conversion_errors(tmp_path):
    svg = tmp_path / "malformed.svg"
    svg.write_text("<not-svg>", encoding="utf-8")

    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        with pytest.raises(ValueError, match="SVG conversion failed"):
            report.place_svg(
                page, rect_mm(10, 10, 100, 50), svg, "part.svg"
            )


def test_svg_placement_rejects_duplicate_id_after_one_marker(tmp_path):
    svg = tmp_path / "part.svg"
    svg.write_text(SVG, encoding="utf-8")

    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        rect = rect_mm(10, 10, 100, 50)
        report.place_svg(page, rect, svg, "part.svg")

        with pytest.raises(
            ValueError, match="drawing already placed: part.svg"
        ):
            report.place_svg(page, rect, svg, "part.svg")

        assert report.placed_drawing_ids == ["part.svg"]
        assert page.get_text().count("DRAWING_ID:part.svg") == 1


def test_marker_failure_poisoning_prevents_reuse_and_save(tmp_path):
    svg = tmp_path / "part.svg"
    svg.write_text(SVG, encoding="utf-8")
    marker_error = RuntimeError("marker insertion failed")

    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        failing_page = FaultInjectingPage(page, insert_error=marker_error)
        rect = rect_mm(10, 10, 100, 50)

        with pytest.raises(RuntimeError, match="marker insertion failed"):
            report.place_svg(failing_page, rect, svg, "part.svg")

        assert report.placed_drawing_ids == []
        with pytest.raises(
            RuntimeError, match="report unusable after failed placement"
        ):
            report.place_svg(page, rect, svg, "another.svg")
        with pytest.raises(
            RuntimeError, match="report unusable after failed placement"
        ):
            report.save(tmp_path / "poisoned.pdf")

    assert report.document.is_closed


def test_show_failure_records_nothing_and_closes_sources(tmp_path):
    svg = tmp_path / "part.svg"
    svg.write_text(SVG, encoding="utf-8")
    show_error = RuntimeError("show failed")

    with PdfReport() as report:
        page = report.add_a4_landscape_page()
        failing_page = FaultInjectingPage(page, show_error=show_error)

        with pytest.raises(RuntimeError, match="show failed"):
            report.place_svg(
                failing_page,
                rect_mm(10, 10, 100, 50),
                svg,
                "part.svg",
            )

        sources = tuple(report._sources)
        assert len(sources) == 2
        assert all(not source.is_closed for source in sources)
        assert report.placed_drawing_ids == []
        assert "DRAWING_ID:" not in page.get_text()

    assert all(source.is_closed for source in sources)
    assert report.document.is_closed


def test_close_is_idempotent_after_source_use(tmp_path):
    svg = tmp_path / "part.svg"
    svg.write_text(SVG, encoding="utf-8")
    report = PdfReport()
    page = report.add_a4_landscape_page()
    report.place_svg(page, rect_mm(10, 10, 100, 50), svg, "part.svg")
    sources = tuple(report._sources)

    report.close()
    report.close()

    assert report.document.is_closed
    assert all(source.is_closed for source in sources)
