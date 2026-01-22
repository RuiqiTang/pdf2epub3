# core/formula_extractor.py
import re
from .models import PageContent, FormulaBlock, TextBlock


class FormulaExtractor:
    """数学公式提取器 - 从文本中识别和提取数学公式"""
    
    def __init__(self):
        # 数学公式模式（LaTeX、MathML、或数学符号）
        self._math_patterns = [
            r'\$[^$]+\$',  # LaTeX内联公式 $...$
            r'\$\$[^$]+\$\$',  # LaTeX块级公式 $$...$$
            r'\\begin\{equation\}.*?\\end\{equation\}',  # LaTeX equation环境
            r'\\begin\{align\}.*?\\end\{align\}',  # LaTeX align环境
            r'\\begin\{matrix\}.*?\\end\{matrix\}',  # LaTeX matrix环境
        ]
        
        # 数学符号模式（用于检测可能的公式）
        self._math_symbols = [
            r'[∑∫√≤≥≠±×÷αβγπθλμσ∞∂]',  # 常见数学符号
            r'\\[a-zA-Z]+\{',  # LaTeX命令
            r'\^\{[^}]+\}',  # 上标
            r'_\{[^}]+\}',  # 下标
        ]

    def extract(self, page: PageContent) -> PageContent:
        """
        从页面内容中提取数学公式
        
        Args:
            page: 页面内容
            
        Returns:
            更新后的页面内容，包含提取的公式
        """
        new_blocks = []
        
        for block in page.blocks:
            if isinstance(block, TextBlock):
                text = block.content
                
                # 检测并提取LaTeX公式
                formulas_found = False
                remaining_text = text
                
                # 查找所有可能的公式
                for pattern in self._math_patterns:
                    matches = re.finditer(pattern, text, re.DOTALL)
                    last_end = 0
                    
                    for match in matches:
                        # 添加公式前的文本
                        before_text = remaining_text[last_end:match.start()].strip()
                        if before_text:
                            new_blocks.append(TextBlock(content=before_text))
                        
                        # 添加公式
                        formula_text = match.group(0)
                        # 清理LaTeX标记
                        if formula_text.startswith('$$'):
                            formula_text = formula_text[2:-2]
                        elif formula_text.startswith('$'):
                            formula_text = formula_text[1:-1]
                        
                        new_blocks.append(FormulaBlock(content=formula_text, inline=True))
                        formulas_found = True
                        last_end = match.end()
                    
                    if formulas_found:
                        # 添加剩余的文本
                        remaining_text = remaining_text[last_end:]
                
                # 如果没有找到标准格式的公式，尝试检测包含数学符号的文本
                if not formulas_found:
                    # 检查是否包含数学符号
                    has_math = any(re.search(pattern, text) for pattern in self._math_symbols)
                    if has_math:
                        # 可能是公式，但格式不标准
                        # 可以尝试转换为LaTeX或保持原样
                        new_blocks.append(TextBlock(content=text))
                    else:
                        # 普通文本
                        new_blocks.append(block)
                elif remaining_text.strip():
                    # 还有剩余文本
                    new_blocks.append(TextBlock(content=remaining_text.strip()))
            else:
                # 非文本块（如已经是公式块），直接添加
                new_blocks.append(block)
        
        # 如果所有块都被处理为空，保留原始块
        if not new_blocks:
            new_blocks = page.blocks
        
        return PageContent(page_number=page.page_number, blocks=new_blocks)