from pathlib import Path
from ebooklib import epub

from .models import PageContent, TextBlock, FormulaBlock


class EPUBBuilder:
    def __init__(self, title: str, author: str):
        self._book = epub.EpubBook()
        self._book.set_title(title)
        self._book.add_author(author)
        self._book.set_language("zh")
        self._chapters: list[epub.EpubHtml] = []

    def add_page(self, page: PageContent) -> None:
        body_parts: list[str] = []

        for block in page.blocks:
            if isinstance(block, TextBlock):
                text = block.content.strip()
                if text:
                    body_parts.append(f"<p>{text}</p>")

            elif isinstance(block, FormulaBlock):
                formula = block.content.strip()
                if formula:
                    # ⚠️ 暂时包在 div 中，避免 lxml namespace 解析炸掉
                    body_parts.append(
                        "<div class='formula'>"
                        f"<math xmlns='http://www.w3.org/1998/Math/MathML'>{formula}</math>"
                        "</div>"
                    )

        # 🚨 强制兜底：绝不允许空 body
        if not body_parts:
            body_parts.append("<p> </p>")

        body_html = "\n".join(body_parts)

        xhtml = (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
            "<!DOCTYPE html>\n"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\">\n"
            "<head>\n"
            f"  <title>Page {page.page_number}</title>\n"
            "  <meta charset=\"utf-8\" />\n"
            "</head>\n"
            "<body>\n"
            f"{body_html}\n"
            "</body>\n"
            "</html>"
        )

        # 🚨 最后一道保险：字符串级校验
        if not xhtml.strip():
            return

        chapter = epub.EpubHtml(
            title=f"Page {page.page_number}",
            file_name=f"page_{page.page_number}.xhtml",
            content=xhtml,
        )

        self._book.add_item(chapter)
        self._chapters.append(chapter)

    def build(self, output_path: Path) -> None:
        # 🚨 再次过滤：防止任何空章节进入 book
        valid_chapters = []
        for ch in self._chapters:
            content = ch.get_content()
            if content and content.strip():
                valid_chapters.append(ch)

        if not valid_chapters:
            raise RuntimeError("No valid EPUB chapters generated")

        self._book.toc = valid_chapters
        self._book.spine = ["nav"] + valid_chapters

        self._book.add_item(epub.EpubNcx())
        self._book.add_item(epub.EpubNav())

        epub.write_epub(output_path, self._book)
