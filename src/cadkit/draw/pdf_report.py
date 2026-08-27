from pathlib import Path

import pymupdf

MM_TO_PT = 72 / 25.4
A4_LANDSCAPE_MM = (297.0, 210.0)
A4_PORTRAIT_MM = (210.0, 297.0)
DEFAULT_FONT = pymupdf.Font("figo")


def mm(value: float) -> float:
    return value * MM_TO_PT


def rect_mm(
    x: float, y: float, width: float, height: float
) -> pymupdf.Rect:
    return pymupdf.Rect(mm(x), mm(y), mm(x + width), mm(y + height))


class PdfReport:
    def __init__(self):
        self.document = pymupdf.open()
        self._sources = []
        self.placed_drawing_ids = []
        self._placement_failed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def add_a4_landscape_page(self):
        return self.document.new_page(
            width=mm(A4_LANDSCAPE_MM[0]),
            height=mm(A4_LANDSCAPE_MM[1]),
        )

    def add_a4_portrait_page(self):
        """A4 the other way up, for drawings that are taller than they are wide.

        An exploded view of a tall module comes out about 3:4; landscape
        wastes more than half the sheet on it.
        """
        return self.document.new_page(
            width=mm(A4_PORTRAIT_MM[0]),
            height=mm(A4_PORTRAIT_MM[1]),
        )

    def textbox(
        self,
        page,
        rect,
        text,
        *,
        fontsize=8,
        fontname="FiraGO",
        **kwargs,
    ):
        if fontname == "FiraGO":
            page.insert_font(fontname=fontname, fontbuffer=DEFAULT_FONT.buffer)
        remaining = page.insert_textbox(
            rect,
            text,
            fontsize=fontsize,
            fontname=fontname,
            encoding=pymupdf.TEXT_ENCODING_LATIN,
            **kwargs,
        )
        if remaining < 0:
            raise ValueError(f"text does not fit: {text!r}")
        return remaining

    def place_svg(self, page, rect, svg_path, drawing_id):
        self._ensure_usable()
        path = Path(svg_path)
        if drawing_id in self.placed_drawing_ids:
            raise ValueError(f"drawing already placed: {drawing_id}")
        if not path.is_file():
            raise ValueError(f"SVG missing: {path}")

        data = path.read_bytes()
        if not data:
            raise ValueError(f"SVG is empty: {path}")

        svg = None
        source = None
        try:
            svg = pymupdf.open(stream=data, filetype="svg")
            source = pymupdf.open(
                stream=svg.convert_to_pdf(), filetype="pdf"
            )
        except Exception as error:
            if source is not None:
                source.close()
            if svg is not None:
                svg.close()
            raise ValueError(f"SVG conversion failed: {path}") from error

        self._sources.extend((svg, source))
        page.show_pdf_page(rect, source, 0, keep_proportion=True)
        try:
            page.insert_text(
                pymupdf.Point(1, 1),
                f"DRAWING_ID:{drawing_id}",
                fontsize=1,
                render_mode=3,
            )
        except Exception:
            self._placement_failed = True
            raise
        self.placed_drawing_ids.append(drawing_id)

    def save(self, path):
        self._ensure_usable()
        self.document.save(path, no_new_id=True)

    def _ensure_usable(self):
        if self._placement_failed:
            raise RuntimeError("report unusable after failed placement")

    def close(self):
        for source in reversed(self._sources):
            if not source.is_closed:
                source.close()
        self._sources.clear()
        if not self.document.is_closed:
            self.document.close()
