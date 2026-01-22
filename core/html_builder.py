from pathlib import Path
from typing import Optional
from .models import PageContent, TextBlock, FormulaBlock


class HTMLBuilder:
    def __init__(self, title: str, output_path: Optional[Path] = None, streaming: bool = False):
        """
        初始化HTML构建器
        
        Args:
            title: 文档标题
            output_path: 输出路径（流式模式必需）
            streaming: 是否启用流式模式（每页处理完立即写入）
        """
        self._title = title
        self._pages: list[PageContent] = []
        self._output_path = output_path
        self._streaming = streaming
        self._file_handle = None
        self._header_written = False
        self._current_page = None  # 当前正在写入的页码

    def add_page(self, page: PageContent) -> None:
        """添加页面（流式模式下会立即写入）"""
        self._pages.append(page)
        
        if self._streaming and self._output_path:
            self._write_page_streaming(page)
    
    def add_block(self, block, page_number: int) -> None:
        """
        添加单个块（块级流式模式）
        
        Args:
            block: TextBlock 或 FormulaBlock
            page_number: 页码
        """
        if not self._streaming or not self._output_path:
            return
        
        # 确保头部已写入
        if not self._header_written:
            self._write_header()
            self._header_written = True
        
        # 检查是否需要开始新页面
        if not hasattr(self, '_current_page') or self._current_page != page_number:
            # 新页面开始
            if hasattr(self, '_current_page') and self._current_page is not None:
                # 关闭上一个页面
                if self._file_handle:
                    self._file_handle.write('        </div>\n      </article>\n')
                    self._file_handle.flush()
            
            # 开始新页面
            self._current_page = page_number
            if self._file_handle:
                page_start = f'      <article class="page">\n        <div class="page-header">\n          <span class="page-number">Page {page_number}</span>\n        </div>\n        <div class="page-content">\n'
                self._file_handle.write(page_start)
                self._file_handle.flush()
        
        # 写入块
        block_html = self._render_block(block)
        if self._file_handle:
            self._file_handle.write(block_html)
            self._file_handle.flush()

    def _write_page_streaming(self, page: PageContent) -> None:
        """流式写入单页"""
        if not self._header_written:
            self._write_header()
            self._header_written = True
        
        # 写入页面内容
        page_html = self._render_page(page)
        if self._file_handle:
            self._file_handle.write(page_html)
            self._file_handle.flush()  # 立即刷新到磁盘

    def _write_header(self) -> None:
        """写入HTML头部"""
        if not self._output_path:
            return
        
        # 打开文件（追加模式）
        self._file_handle = open(self._output_path, 'w', encoding='utf-8')
        
        # 写入HTML头部
        header = self._get_html_header()
        self._file_handle.write(header)
        self._file_handle.flush()

    def _get_html_header(self) -> str:
        """获取HTML头部内容"""
        html_parts = []
        
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="zh-CN">')
        html_parts.append('<head>')
        html_parts.append('  <meta charset="UTF-8">')
        html_parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_parts.append(f'  <title>{self._title}</title>')
        html_parts.append('  <style>')
        html_parts.append(self._get_css_styles())
        html_parts.append('  </style>')
        html_parts.append('</head>')
        html_parts.append('<body>')
        html_parts.append('  <div class="document-wrapper">')
        html_parts.append('    <header class="document-header">')
        html_parts.append(f'      <h1 class="document-title">{self._title}</h1>')
        html_parts.append('    </header>')
        html_parts.append('    <div class="document-content">')
        
        return '\n'.join(html_parts) + '\n'
    
    def _get_css_styles(self) -> str:
        """获取CSS样式（从原有build方法中提取）"""
        # 这里复用原有的CSS样式代码
        # 为了简化，直接从原有代码中提取
        return '''    /* Bridgewater Associates 官方设计规范 - 完全对齐 */
    /* 参考: https://www.bridgewater.com/research-and-insights/investing-in-a-new-world-capturing-opportunity-and-weathering-uncertainty */
    :root {
      /* 字体系统 - 优雅衬线字体 */
      --font-family-base: "Times New Roman", Times, "Liberation Serif", "Nimbus Roman No9 L", "DejaVu Serif", serif;
      --font-family-heading: "Times New Roman", Times, serif;
      --font-size-base: 16px;
      --font-size-h1: 36px;
      --font-size-h2: 28px;
      --font-size-h3: 22px;
      --font-size-small: 14px;
      /* 行高系统 - 1.4-1.6倍标准 */
      --line-height-base: 1.5;
      --line-height-heading: 1.3;
      /* 字间距系统 */
      --letter-spacing-base: 0.02em;
      --letter-spacing-heading: 0.03em;
      /* 颜色系统 - Bridgewater 标准 */
      --color-text: #111;
      --color-bg: #fff;
      --color-border: #e5e5e5;
      --color-text-muted: #666;
      /* 8px 栅格系统 */
      --spacing-unit: 8px;
      --spacing-xs: calc(var(--spacing-unit) * 1);
      --spacing-sm: calc(var(--spacing-unit) * 2);
      --spacing-md: calc(var(--spacing-unit) * 3);
      --spacing-lg: calc(var(--spacing-unit) * 6);
      --spacing-xl: calc(var(--spacing-unit) * 10);
      /* 布局系统 */
      --max-width: 720px;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      font-family: var(--font-family-base);
      font-size: var(--font-size-base);
      line-height: var(--line-height-base);
      letter-spacing: var(--letter-spacing-base);
      color: var(--color-text);
      background: var(--color-bg);
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      padding: 0;
      margin: 0;
    }
    .document-wrapper {
      max-width: var(--max-width);
      margin: 0 auto;
      padding: var(--spacing-xl) var(--spacing-md);
    }
    .document-header {
      margin-bottom: var(--spacing-xl);
      padding-bottom: var(--spacing-md);
      border-bottom: 1px solid var(--color-border);
    }
    .document-title {
      font-family: var(--font-family-heading);
      font-size: var(--font-size-h1);
      font-weight: 400;
      line-height: var(--line-height-heading);
      letter-spacing: var(--letter-spacing-heading);
      color: var(--color-text);
      margin-bottom: 0;
    }
    .page {
      margin-bottom: var(--spacing-xl);
      page-break-after: always;
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: var(--spacing-lg);
      padding-bottom: var(--spacing-sm);
      border-bottom: 1px solid var(--color-border);
    }
    .page-number {
      font-size: var(--font-size-small);
      font-weight: 500;
      color: var(--color-text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .page-content {
      color: var(--color-text);
    }
    .page-content p {
      margin-bottom: var(--spacing-md);
      text-align: left;
      font-size: var(--font-size-base);
      line-height: var(--line-height-base);
      letter-spacing: var(--letter-spacing-base);
      color: var(--color-text);
      font-weight: 400;
    }
    .page-content p:last-child {
      margin-bottom: 0;
    }
    .page-content h2 {
      font-family: var(--font-family-heading);
      font-size: var(--font-size-h2);
      font-weight: 400;
      line-height: var(--line-height-heading);
      letter-spacing: var(--letter-spacing-heading);
      color: var(--color-text);
      margin-top: var(--spacing-lg);
      margin-bottom: var(--spacing-md);
    }
    .page-content h3 {
      font-family: var(--font-family-heading);
      font-size: var(--font-size-h3);
      font-weight: 400;
      line-height: var(--line-height-heading);
      letter-spacing: var(--letter-spacing-heading);
      color: var(--color-text);
      margin-top: var(--spacing-md);
      margin-bottom: var(--spacing-sm);
    }
    .formula {
      margin: var(--spacing-lg) 0;
      padding: var(--spacing-md);
      background: #fafafa;
      border-left: 3px solid var(--color-text);
      border-radius: 2px;
      overflow-x: auto;
    }
    .formula math {
      display: block;
      text-align: center;
      font-size: var(--font-size-base);
      line-height: var(--line-height-base);
    }
    @media (max-width: 768px) {
      .document-wrapper {
        padding: var(--spacing-lg) var(--spacing-sm);
      }
      .document-title {
        font-size: 32px;
      }
      .page-content h2 {
        font-size: 24px;
      }
      .page-content h3 {
        font-size: 20px;
      }
    }
    @media print {
      body { background: white; }
      .document-wrapper { padding: 20px; }
      .page { page-break-after: always; }
      .page-header { border-bottom: 1px solid #ddd; }
    }'''

    def _render_block(self, block) -> str:
        """渲染单个块为HTML"""
        if isinstance(block, TextBlock):
            text = block.content.strip()
            if text:
                # 转义HTML
                text = self._escape_html(text)
                return f'          <p>{text}</p>\n'
        elif isinstance(block, FormulaBlock):
            formula = block.content.strip()
            if formula:
                formula = self._escape_html(formula)
                return f'          <div class="formula">\n            <math xmlns="http://www.w3.org/1998/Math/MathML">{formula}</math>\n          </div>\n'
        return ''
    
    def _render_page(self, page: PageContent) -> str:
        """渲染单页为HTML"""
        html_parts = []
        
        html_parts.append('      <article class="page">')
        html_parts.append('        <div class="page-header">')
        html_parts.append(f'          <span class="page-number">Page {page.page_number}</span>')
        html_parts.append('        </div>')
        html_parts.append('        <div class="page-content">')
        
        body_parts = []
        for block in page.blocks:
            if isinstance(block, TextBlock):
                text = block.content.strip()
                if text:
                    # 将换行符转换为段落
                    paragraphs = text.split('\n\n')
                    for para in paragraphs:
                        para = para.strip()
                        if para:
                            # 处理单行换行，转换为空格
                            para = ' '.join(para.split('\n'))
                            body_parts.append(f'          <p>{self._escape_html(para)}</p>')
            
            elif isinstance(block, FormulaBlock):
                formula = block.content.strip()
                if formula:
                    body_parts.append('          <div class="formula">')
                    body_parts.append(f'            <math xmlns="http://www.w3.org/1998/Math/MathML">{self._escape_html(formula)}</math>')
                    body_parts.append('          </div>')
        
        # 如果页面为空，添加占位符
        if not body_parts:
            body_parts.append('          <p style="color: var(--color-text-muted); font-style: italic;">（此页无内容）</p>')
        
        html_parts.extend(body_parts)
        html_parts.append('        </div>')
        html_parts.append('      </article>')
        
        return '\n'.join(html_parts) + '\n'

    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))

    def build(self, output_path: Optional[Path] = None) -> None:
        """构建HTML文件（非流式模式）"""
        if self._streaming:
            # 流式模式下，关闭当前页面（如果有）并写入尾部
            if hasattr(self, '_current_page') and self._current_page is not None:
                if self._file_handle:
                    self._file_handle.write('        </div>\n      </article>\n')
                    self._file_handle.flush()
            
            self._write_footer()
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None
            return
        
        # 非流式模式：使用原有逻辑
        if output_path is None:
            output_path = self._output_path
        if output_path is None:
            raise ValueError("output_path must be provided")
        
        # 确保至少有一个页面
        if not self._pages:
            self._pages.append(PageContent(
                page_number=1,
                blocks=[TextBlock(content="（无内容）")]
            ))
        
        html_parts = []
        
        # HTML 头部
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="zh-CN">')
        html_parts.append('<head>')
        html_parts.append('  <meta charset="UTF-8">')
        html_parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html_parts.append(f'  <title>{self._title}</title>')
        html_parts.append('  <style>')
        html_parts.append(self._get_css_styles())
        html_parts.append('  </style>')
        html_parts.append('</head>')
        html_parts.append('<body>')
        html_parts.append('  <div class="document-wrapper">')
        html_parts.append('    <header class="document-header">')
        html_parts.append(f'      <h1 class="document-title">{self._title}</h1>')
        html_parts.append('    </header>')
        html_parts.append('    <div class="document-content">')
        
        # 添加所有页面
        for page in self._pages:
            html_parts.append(self._render_page(page))
        
        # HTML 尾部
        html_parts.append('    </div>')
        html_parts.append('  </div>')
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        # 写入文件
        html_content = '\n'.join(html_parts)
        output_path.write_text(html_content, encoding='utf-8')
    
    def _write_footer(self) -> None:
        """写入HTML尾部"""
        if self._file_handle:
            footer = '    </div>\n  </div>\n</body>\n</html>\n'
            self._file_handle.write(footer)
            self._file_handle.flush()
