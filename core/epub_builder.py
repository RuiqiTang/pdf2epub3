from pathlib import Path
import re
from ebooklib import epub
from lxml import etree

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
        # 使用可见文本作为占位符，避免 lxml 解析错误（空文档错误）
        if not body_parts:
            body_parts.append("<p>（此页无内容）</p>")

        body_html = "\n".join(body_parts)
        
        # 验证 body_html 不为空（去除空白字符后）
        # 如果只有空白字符，使用占位符
        if not body_html.strip() or len(body_html.strip()) < 10:
            body_parts = ["<p>（此页无内容）</p>"]
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
        
        # 使用 lxml 验证 XHTML 内容，确保它可以被正确解析且 body 不为空
        try:
            parser = etree.XMLParser(recover=True)
            tree = etree.fromstring(xhtml.encode('utf-8'), parser=parser)
            # 检查 body 标签是否有内容（子元素或文本）
            body_elements = tree.xpath('//xhtml:body', namespaces={'xhtml': 'http://www.w3.org/1999/xhtml'})
            if not body_elements:
                # 没有找到 body 标签，使用占位符
                raise ValueError("No body element found")
            
            body = body_elements[0]
            # 检查 body 是否有子元素或文本内容
            has_children = len(body) > 0
            has_text = body.text and body.text.strip()
            has_tail = any(child.tail and child.tail.strip() for child in body)
            
            if not (has_children or has_text or has_tail):
                # body 为空，使用占位符
                xhtml = (
                    "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                    "<!DOCTYPE html>\n"
                    "<html xmlns=\"http://www.w3.org/1999/xhtml\">\n"
                    "<head>\n"
                    f"  <title>Page {page.page_number}</title>\n"
                    "  <meta charset=\"utf-8\" />\n"
                    "</head>\n"
                    "<body><p>（此页无内容）</p></body>\n"
                    "</html>"
                )
        except Exception as e:
            # 如果解析失败或 body 为空，使用最小有效内容
            print(f"Warning: Failed to validate XHTML for page {page.page_number}: {e}")
            xhtml = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                "<!DOCTYPE html>\n"
                "<html xmlns=\"http://www.w3.org/1999/xhtml\">\n"
                "<head>\n"
                f"  <title>Page {page.page_number}</title>\n"
                "  <meta charset=\"utf-8\" />\n"
                "</head>\n"
                "<body><p>（此页无内容）</p></body>\n"
                "</html>"
            )

        # 创建章节并添加到书籍和章节列表
        chapter = epub.EpubHtml(
            title=f"Page {page.page_number}",
            file_name=f"page_{page.page_number}.xhtml",
            content=xhtml,
        )
        
        # 立即验证 get_body_content() 是否返回有效内容
        try:
            body_content = chapter.get_body_content()
            if not body_content or not body_content.strip():
                # 如果 get_body_content() 返回空，说明 XHTML 格式可能有问题
                # 使用更简单的格式重新创建
                print(f"Warning: Page {page.page_number} get_body_content() returns empty, using simpler format")
                xhtml = (
                    "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                    "<!DOCTYPE html>\n"
                    "<html xmlns=\"http://www.w3.org/1999/xhtml\">\n"
                    "<head>\n"
                    f"  <title>Page {page.page_number}</title>\n"
                    "  <meta charset=\"utf-8\" />\n"
                    "</head>\n"
                    "<body><p>（此页无内容）</p></body>\n"
                    "</html>"
                )
                chapter.set_content(xhtml)
                # 再次验证
                body_content = chapter.get_body_content()
                if not body_content or not body_content.strip():
                    print(f"Error: Page {page.page_number} get_body_content() still returns empty after fix")
        except Exception as e:
            print(f"Warning: Failed to verify get_body_content() for page {page.page_number}: {e}")

        self._book.add_item(chapter)
        self._chapters.append(chapter)

    def build(self, output_path: Path) -> None:
        # 确保至少有一个章节
        if not self._chapters:
            raise RuntimeError("No chapters added to EPUB")

        # 在写入前验证所有章节的内容，确保 get_body_content() 返回有效内容
        # 这是关键：ebooklib 在生成导航时会调用 get_body_content()，如果返回空就会报错
        # 使用更简单的 XHTML 格式，确保 get_body_content() 能正确提取 body 内容
        minimal_xhtml_template = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml">\n'
            '<head>\n'
            '  <title>{title}</title>\n'
            '  <meta charset="utf-8"/>\n'
            '</head>\n'
            '<body>\n'
            '  <p>（此页无内容）</p>\n'
            '</body>\n'
            '</html>'
        )
        
        # 直接测试每个章节的 get_body_content()，这是 ebooklib 实际使用的方法
        chapters_to_recreate = []
        
        for chapter in list(self._chapters):  # 使用 list() 创建副本，避免在迭代时修改
            try:
                body_content = chapter.get_body_content()
                if not body_content or not body_content.strip():
                    # get_body_content() 返回空，需要修复
                    print(f"Warning: Chapter {chapter.file_name} get_body_content() returns empty, will recreate")
                    chapters_to_recreate.append(chapter)
            except Exception as e:
                # 如果调用 get_body_content() 时出错，也需要修复
                print(f"Warning: Failed to call get_body_content() for {chapter.file_name}: {e}, will recreate")
                chapters_to_recreate.append(chapter)
        
        # 重新创建所有有问题的章节
        for chapter in chapters_to_recreate:
            minimal_xhtml = minimal_xhtml_template.format(title=chapter.title)
            
            # 移除旧章节
            if chapter in self._book.items:
                self._book.items.remove(chapter)
            if chapter in self._chapters:
                self._chapters.remove(chapter)
            
            # 创建新章节，使用已知有效的格式
            new_chapter = epub.EpubHtml(
                title=chapter.title,
                file_name=chapter.file_name,
                content=minimal_xhtml,
            )
            
            # 立即验证新章节的 get_body_content() 是否返回有效内容
            try:
                body_content = new_chapter.get_body_content()
                if not body_content or not body_content.strip():
                    # 如果仍然为空，尝试使用 set_content
                    print(f"Warning: New chapter {new_chapter.file_name} get_body_content() still empty, trying set_content")
                    new_chapter.set_content(minimal_xhtml)
                    body_content = new_chapter.get_body_content()
                    if not body_content or not body_content.strip():
                        print(f"Error: Chapter {new_chapter.file_name} get_body_content() still returns empty!")
            except Exception as e:
                print(f"Warning: Failed to verify new chapter {new_chapter.file_name}: {e}")
            
            self._book.add_item(new_chapter)
            self._chapters.append(new_chapter)
        
        # 最终验证：确保所有章节的 get_body_content() 都返回有效内容
        print(f"Final validation: Checking {len(self._chapters)} chapters...")
        final_fixes = []
        for chapter in list(self._chapters):
            try:
                body_content = chapter.get_body_content()
                if not body_content or not body_content.strip():
                    print(f"ERROR: Chapter {chapter.file_name} get_body_content() still returns empty in final check!")
                    final_fixes.append(chapter)
            except Exception as e:
                print(f"ERROR: Failed to get_body_content() for {chapter.file_name} in final check: {e}")
                final_fixes.append(chapter)
        
        # 如果有章节在最终检查中仍然失败，完全重新创建它们
        # 使用一个已知可以工作的简单 XHTML 格式
        simple_xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml">\n'
            '<head><title>Page</title><meta charset="utf-8"/></head>\n'
            '<body><p>Content</p></body>\n'
            '</html>'
        )
        
        for chapter in final_fixes:
            # 完全移除旧章节
            if chapter in self._book.items:
                self._book.items.remove(chapter)
            if chapter in self._chapters:
                self._chapters.remove(chapter)
            
            # 创建全新的章节，使用最简单的格式
            new_chapter = epub.EpubHtml(
                title=chapter.title,
                file_name=chapter.file_name,
                content=simple_xhtml.replace('Page', chapter.title).replace('Content', '（此页无内容）'),
            )
            
            # 多次尝试设置内容，确保被正确设置
            content_str = simple_xhtml.replace('Page', chapter.title).replace('Content', '（此页无内容）')
            new_chapter.set_content(content_str)
            
            # 尝试直接设置内部属性
            try:
                if hasattr(new_chapter, 'content'):
                    new_chapter.content = content_str.encode('utf-8') if isinstance(content_str, str) else content_str
            except:
                pass
            
            try:
                if hasattr(new_chapter, '_content'):
                    new_chapter._content = content_str.encode('utf-8') if isinstance(content_str, str) else content_str
            except:
                pass
            
            # 添加到书籍和章节列表
            self._book.add_item(new_chapter)
            self._chapters.append(new_chapter)
            
            # 最后验证
            try:
                body_content = new_chapter.get_body_content()
                if body_content and body_content.strip():
                    print(f"Success: Chapter {new_chapter.file_name} get_body_content() now returns content")
                else:
                    print(f"Warning: Chapter {new_chapter.file_name} get_body_content() still returns empty after all fixes")
            except Exception as e:
                print(f"Warning: Failed to verify {new_chapter.file_name}: {e}")

        # 使用所有已添加的章节
        self._book.toc = self._chapters
        self._book.spine = ["nav"] + self._chapters

        self._book.add_item(epub.EpubNcx())
        self._book.add_item(epub.EpubNav())

        epub.write_epub(output_path, self._book)
