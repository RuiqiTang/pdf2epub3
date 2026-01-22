# core/pdf_loader.py
from pathlib import Path
from typing import Iterator
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar


class PDFPageLoader:
    def __init__(self, pdf_path: Path):
        self._pdf_path = pdf_path

    def iter_pages(self) -> Iterator[list]:
        for layout in extract_pages(self._pdf_path):
            yield list(layout)
