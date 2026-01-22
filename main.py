# main.py
from pathlib import Path
from typing import Optional, List

from core.pdf_loader import PDFPageLoader
from core.page_parser import PDFPageParser
from core.formula_extractor import FormulaExtractor
from core.epub_builder import EPUBBuilder
from core.html_builder import HTMLBuilder
from core.models import PageContent, TextBlock
from ui.progress import ProgressCallback


class PDFToEPUBPipeline:
    def __init__(
        self,
        pdf_path: Path,
        output_path: Path,
        progress_callback: Optional[ProgressCallback] = None,
        output_format: str = "html",  # "html" 或 "epub"
        use_ocr: bool = False,  # 是否使用OCR
        ocr_backend: str = "paddleocr",  # OCR后端
    ):
        self._loader = PDFPageLoader(pdf_path, use_ocr=use_ocr)
        self._parser = PDFPageParser(use_ocr=use_ocr, ocr_backend=ocr_backend, progress_callback=progress_callback)
        self._formula = FormulaExtractor()
        self._output_format = output_format.lower()
        
        if self._output_format == "html":
            # 启用流式模式
            self._builder = HTMLBuilder(
                title=pdf_path.stem, 
                output_path=output_path,
                streaming=True
            )
        else:
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
        # 流式处理：逐页处理并立即写入
        raw_pages = list(self._loader.iter_pages())
        total_pages = len(raw_pages)

        if self._progress:
            self._progress.on_start(total_pages)

        # 流式模式：逐页处理并立即写入（支持按块流式输出）
        for idx, layout in enumerate(raw_pages, start=1):
            # 定义块回调：每识别到一个块就立即输出并更新预览
            def block_callback(block, page_num):
                """块级流式回调：立即写入HTML并更新预览"""
                # 应用公式提取（如果需要）
                if hasattr(block, 'content'):
                    # 这里可以添加公式检测逻辑
                    pass
                # 立即写入HTML
                self._builder.add_block(block, page_num)
                # 立即更新UI预览（识别完一段就显示）
                if self._progress and hasattr(self._progress, 'render_preview'):
                    self._progress.render_preview()
            
            # 解析页面（带块回调，实现按块流式输出）
            page = self._parser.parse(idx, layout, block_callback=block_callback)
            page = self._formula.extract(page)
            
            # 如果还有未通过回调处理的块，也添加到builder
            # （非OCR模式或块回调未处理的情况）
            if page.blocks:
                self._builder.add_page(page)

            if self._progress:
                self._progress.on_page_processed(idx)

        # 完成构建（流式模式下写入尾部并关闭文件）
        self._builder.build(self._output_path)

        if self._progress:
            self._progress.on_finish(str(self._output_path))