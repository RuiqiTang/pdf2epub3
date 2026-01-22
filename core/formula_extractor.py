# core/formula_extractor.py
from .models import PageContent, FormulaBlock


class FormulaExtractor:
    def extract(self, page: PageContent) -> PageContent:
        """
        占位实现：
        - 后续可插入 MathML / OCR / LaTeX-OCR
        """
        return page