# core/models.py
from dataclasses import dataclass
from typing import List


@dataclass
class FormulaBlock:
    content: str           # LaTeX or MathML
    inline: bool = False


@dataclass
class TextBlock:
    content: str


@dataclass
class PageContent:
    page_number: int
    blocks: List[object]   # TextBlock | FormulaBlock