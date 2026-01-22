# core/pdf_loader.py
from pathlib import Path
from typing import Iterator, Optional
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar
from PIL import Image
import io
import subprocess
from typing import Union


class PDFPageLoader:
    def __init__(self, pdf_path: Path, use_ocr: bool = False):
        """
        初始化PDF页面加载器
        
        Args:
            pdf_path: PDF文件路径
            use_ocr: 是否使用OCR（用于扫描版PDF）
        """
        self._pdf_path = pdf_path
        self._use_ocr = use_ocr
        
        if self._use_ocr:
            try:
                from pdf2image import convert_from_path
                # 检查 poppler 是否可用
                try:
                    # 尝试检查 poppler 是否在 PATH 中
                    result = subprocess.run(
                        ['pdftoppm', '-v'],
                        capture_output=True,
                        timeout=2
                    )
                    self._pdf2image = convert_from_path
                    self._poppler_available = True
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    # poppler 未安装或不在 PATH 中
                    self._poppler_available = False
                    self._use_ocr = False
                    raise RuntimeError(
                        "Poppler 未安装。\n"
                        "macOS: brew install poppler\n"
                        "Linux: sudo apt-get install poppler-utils\n"
                        "Windows: 下载 poppler 并添加到 PATH"
                    )
            except ImportError:
                self._use_ocr = False
                raise RuntimeError(
                    "pdf2image 未安装。\n"
                    "请安装: pip install pdf2image\n"
                    "还需要安装 poppler:\n"
                    "  macOS: brew install poppler\n"
                    "  Linux: sudo apt-get install poppler-utils"
                )

    def iter_pages(self) -> Iterator[Union[list, Image.Image]]:
        """
        迭代PDF页面
        
        Returns:
            如果启用OCR，返回 PIL Image 对象
            如果未启用OCR，返回 pdfminer 的 layout 列表
        """
        if self._use_ocr:
            # OCR模式：将PDF转换为图像
            try:
                images = self._pdf2image(self._pdf_path, dpi=200)
                for image in images:
                    yield image  # 直接返回PIL Image对象
            except Exception as e:
                error_msg = str(e)
                if "poppler" in error_msg.lower() or "Unable to get page count" in error_msg:
                    raise RuntimeError(
                        f"OCR模式失败: {error_msg}\n\n"
                        "请安装 poppler:\n"
                        "  macOS: brew install poppler\n"
                        "  Linux: sudo apt-get install poppler-utils\n"
                        "  Windows: 下载 poppler 并添加到 PATH\n\n"
                        "安装后请重启应用。"
                    ) from e
                else:
                    raise RuntimeError(f"OCR模式失败: {error_msg}") from e
        else:
            # 文本提取模式：直接提取文本
            for layout in extract_pages(self._pdf_path):
                yield list(layout)
