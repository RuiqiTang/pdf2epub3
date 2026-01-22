# core/page_parser.py
from typing import List, Union, Callable, Optional
from pdfminer.layout import LTTextContainer
from PIL import Image
from .models import PageContent, TextBlock, FormulaBlock
from .ocr_engine import OCREngine
from .image_splitter import ImageSplitter


class PDFPageParser:
    def __init__(self, use_ocr: bool = False, ocr_backend: str = "paddleocr", progress_callback=None):
        """
        初始化PDF页面解析器
        
        Args:
            use_ocr: 是否使用OCR（启用后整页使用OCR识别）
            ocr_backend: OCR后端，可选 "paddleocr", "easyocr", "tesseract"
            progress_callback: 可选的进度回调函数
        """
        self._use_ocr = use_ocr
        self._ocr_engine = OCREngine(backend=ocr_backend) if use_ocr else None
        self._progress_callback = progress_callback
        self._image_splitter = ImageSplitter() if use_ocr else None

    def parse(self, page_number: int, layout_items: Union[list, Image.Image], block_callback: Optional[Callable] = None) -> PageContent:
        """
        解析PDF页面（支持按块流式输出）
        
        Args:
            page_number: 页码
            layout_items: 
                - 如果启用OCR，这是 PIL Image
                - 如果未启用OCR，这是 pdfminer 的 layout 列表
            block_callback: 可选的块回调函数，每识别到一个块就调用 (block, page_number)
        """
        blocks: List[object] = []

        # OCR模式：先按行裁剪图片，然后逐个段落OCR并流式输出
        if self._use_ocr and isinstance(layout_items, Image.Image):
            if self._progress_callback:
                self._progress_callback.update(f"第 {page_number} 页：正在分割图片为段落...")
            
            # 第一步：将页面图片按行分割成段落图片
            line_images = self._image_splitter.split_into_lines(layout_items, self._ocr_engine)
            
            if self._progress_callback:
                self._progress_callback.update(f"第 {page_number} 页：检测到 {len(line_images)} 个段落，开始OCR识别...")
            
            # 保存段落图片到test_paragraph文件夹（用于调试）
            import os
            from pathlib import Path
            test_dir = Path("test_paragraph")
            test_dir.mkdir(exist_ok=True)
            page_dir = test_dir / f"page_{page_number}"
            page_dir.mkdir(exist_ok=True)
            
            # 第二步：逐个段落进行OCR，识别完一段就立即输出
            for idx, (line_image, y_start, y_end) in enumerate(line_images, start=1):
                # 保存段落图片
                para_image_path = page_dir / f"paragraph_{idx:03d}_y{y_start}-{y_end}.png"
                line_image.save(para_image_path)
                if self._progress_callback:
                    self._progress_callback.update(f"第 {page_number} 页：段落 {idx} 图片已保存到 {para_image_path}")
                
                if self._progress_callback:
                    self._progress_callback.update(f"第 {page_number} 页：正在识别第 {idx}/{len(line_images)} 个段落...")
                
                # 对当前段落图片进行OCR
                text_results = self._ocr_engine.extract_text_from_image(line_image, self._progress_callback)
                
                # 调试信息
                if self._progress_callback:
                    result_count = len(text_results) if text_results else 0
                    self._progress_callback.update(f"第 {page_number} 页：段落 {idx} OCR完成，结果数: {result_count}")
                
                if text_results:
                    # 过滤并合并文本（降低置信度阈值，避免过滤掉有效结果）
                    filtered_texts = [text for text, conf in text_results if conf > 0.3]
                    
                    if self._progress_callback:
                        self._progress_callback.update(f"第 {page_number} 页：段落 {idx} 过滤后文本数: {len(filtered_texts)}")
                    
                    if filtered_texts:
                        paragraph_text = ' '.join(filtered_texts).strip()
                        
                        if paragraph_text:
                            if self._progress_callback:
                                preview_text = paragraph_text[:50] + "..." if len(paragraph_text) > 50 else paragraph_text
                                self._progress_callback.update(f"第 {page_number} 页：段落 {idx} 识别到文本: {preview_text}")
                            
                            block = TextBlock(content=paragraph_text)
                            blocks.append(block)
                            
                            # 流式回调：立即输出这个段落块
                            if block_callback:
                                if self._progress_callback:
                                    self._progress_callback.update(f"第 {page_number} 页：段落 {idx} 调用block_callback输出")
                                block_callback(block, page_number)
                            else:
                                if self._progress_callback:
                                    self._progress_callback.update(f"第 {page_number} 页：段落 {idx} 警告：block_callback为None")
                else:
                    if self._progress_callback:
                        self._progress_callback.update(f"第 {page_number} 页：段落 {idx} OCR未返回结果")
                
                # 检测当前段落中的数学公式
                formulas = self._ocr_engine.detect_math_formulas(line_image, self._progress_callback)
                for latex, conf, bbox in formulas:
                    if conf > 0.6:
                        block = FormulaBlock(content=latex, inline=False)
                        blocks.append(block)
                        
                        # 流式回调：立即输出这个公式块
                        if block_callback:
                            block_callback(block, page_number)
        
        # 纯文本模式：使用pdfminer提取文本
        else:
            for item in layout_items:
                if isinstance(item, LTTextContainer):
                    text = item.get_text().strip()
                    if text:
                        block = TextBlock(content=text)
                        blocks.append(block)
                        
                        # 流式回调：立即输出这个块
                        if block_callback:
                            block_callback(block, page_number)

        return PageContent(page_number=page_number, blocks=blocks)
