# core/page_parser.py
from typing import List
from pdfminer.layout import LTTextContainer
from .models import PageContent, TextBlock


class PDFPageParser:
    def parse(self, page_number: int, layout_items: list) -> PageContent:
        blocks: List[object] = []

        for item in layout_items:
            if isinstance(item, LTTextContainer):
                text = item.get_text().strip()
                if text:
                    blocks.append(TextBlock(content=text))

        return PageContent(page_number=page_number, blocks=blocks)
