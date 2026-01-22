# main.py
from pathlib import Path
from typing import Optional, List

from core.pdf_loader import PDFPageLoader
from core.page_parser import PDFPageParser
from core.formula_extractor import FormulaExtractor
from core.epub_builder import EPUBBuilder
from core.models import PageContent, TextBlock
from ui.progress import ProgressCallback


class PDFToEPUBPipeline:
    def __init__(
        self,
        pdf_path: Path,
        output_path: Path,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        self._loader = PDFPageLoader(pdf_path)
        self._parser = PDFPageParser()
        self._formula = FormulaExtractor()
        self._builder = EPUBBuilder(
            title=pdf_path.stem,
            author="Unknown",
        )
        self._output_path = output_path
        self._progress = progress_callback

    def _ensure_non_empty_pages(
        self, pages: List[PageContent]
    ) -> List[PageContent]:
        """
        开发阶段兜底：
        - 没有任何页面
        - 或所有页面内容为空
        """
        if not pages:
            return [
                PageContent(
                    page_number=1,
                    blocks=[
                        TextBlock(
                            content=(
                                "This EPUB is a placeholder.\n\n"
                                "No OCR or text extraction is enabled yet."
                            )
                        )
                    ],
                )
            ]

        has_valid_content = any(
            any(
                isinstance(b, TextBlock) and b.content.strip()
                for b in page.blocks
            )
            for page in pages
        )

        if not has_valid_content:
            pages[0].blocks.append(
                TextBlock(
                    content=(
                        "This EPUB is a placeholder.\n\n"
                        "PDF pages were parsed, but no textual content was extracted."
                    )
                )
            )

        return pages

    def run(self) -> None:
        raw_pages = list(self._loader.iter_pages())
        total_pages = len(raw_pages)

        if self._progress:
            self._progress.on_start(total_pages)

        parsed_pages: List[PageContent] = []

        for idx, layout in enumerate(raw_pages, start=1):
            page = self._parser.parse(idx, layout)
            page = self._formula.extract(page)
            parsed_pages.append(page)

            if self._progress:
                self._progress.on_page_processed(idx)

        # 🔑 核心兜底
        parsed_pages = self._ensure_non_empty_pages(parsed_pages)

        for page in parsed_pages:
            self._builder.add_page(page)

        self._builder.build(self._output_path)

        if self._progress:
            self._progress.on_finish(str(self._output_path))