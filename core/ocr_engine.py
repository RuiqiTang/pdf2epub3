# core/ocr_engine.py
"""
OCR引擎 - 支持数学公式识别
支持多种OCR后端：PaddleOCR（推荐）、EasyOCR、Tesseract
"""
from pathlib import Path
from typing import List, Tuple, Optional

try:
    import numpy as np
    from PIL import Image
    HAS_IMAGE_LIBS = True
except ImportError:
    HAS_IMAGE_LIBS = False
    np = None


class OCREngine:
    """OCR引擎，支持文本和数学公式识别"""
    
    def __init__(self, backend: str = "paddleocr"):
        """
        初始化OCR引擎
        
        Args:
            backend: OCR后端，可选 "paddleocr", "easyocr", "tesseract"
        """
        self._backend = backend.lower()
        self._ocr = None
        self._initialized = False
        
    def _initialize(self, progress_callback=None):
        """
        延迟初始化OCR引擎
        
        Args:
            progress_callback: 可选的进度回调函数，用于显示初始化进度
        """
        if self._initialized:
            return
            
        try:
            if self._backend == "paddleocr":
                from paddleocr import PaddleOCR
                
                # 显示初始化提示
                if progress_callback:
                    progress_callback.update("正在初始化 PaddleOCR 引擎（首次使用可能需要几分钟）...")
                else:
                    print("正在初始化 PaddleOCR 引擎（首次使用可能需要几分钟）...")
                
                # 初始化PaddleOCR，支持中英文和数学公式
                # PaddleOCR 3.x 不再支持 use_gpu 参数，默认使用 CPU
                # 如果需要 GPU，可以通过环境变量或 device 参数控制
                # 注意：初始化过程会加载多个模型，可能需要一些时间
                self._ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang='ch',  # 中英文混合
                    # 注意：PaddleOCR 3.x 移除了 use_gpu 参数
                    # 默认使用 CPU，如需 GPU 请参考官方文档配置
                )
                
                if progress_callback:
                    progress_callback.update("PaddleOCR 引擎初始化完成")
                else:
                    print("PaddleOCR 引擎初始化完成")
            elif self._backend == "easyocr":
                if progress_callback:
                    progress_callback.update("正在初始化 EasyOCR 引擎（首次使用可能需要几分钟）...")
                else:
                    print("正在初始化 EasyOCR 引擎（首次使用可能需要几分钟）...")
                import easyocr
                self._ocr = easyocr.Reader(['ch_sim', 'en'], gpu=False)
                if progress_callback:
                    progress_callback.update("EasyOCR 引擎初始化完成")
                else:
                    print("EasyOCR 引擎初始化完成")
            elif self._backend == "tesseract":
                import pytesseract
                self._ocr = pytesseract
            else:
                raise ValueError(f"不支持的OCR后端: {self._backend}")
                
            self._initialized = True
        except ImportError as e:
            error_msg = str(e)
            if "paddle" in error_msg.lower():
                print(f"Warning: PaddleOCR 依赖未完整安装: {error_msg}")
                print("请安装完整依赖:")
                print("  pip install paddlepaddle")
                print("  pip install paddleocr")
            else:
                print(f"Warning: OCR库未安装，将使用基础文本提取: {error_msg}")
                if self._backend == "paddleocr":
                    print("请安装: pip install paddlepaddle paddleocr")
                elif self._backend == "easyocr":
                    print("请安装: pip install easyocr")
                elif self._backend == "tesseract":
                    print("请安装: pip install pytesseract")
                    print("还需要安装系统依赖: brew install tesseract (macOS)")
            self._ocr = None
            self._initialized = True
        except Exception as e:
            print(f"Warning: OCR引擎初始化失败: {e}")
            print("将使用基础文本提取模式")
            self._ocr = None
            self._initialized = True
    
    def extract_text_from_image(self, image, progress_callback=None, stream_callback=None) -> List[Tuple[str, float]]:
        """
        从图像中提取文本
        
        Args:
            image: PIL Image对象或numpy数组
            progress_callback: 可选的进度回调函数
            stream_callback: 可选的流式回调函数，每识别到一个块就调用 (text, confidence, y_position)
            
        Returns:
            List of (text, confidence) tuples
        """
        self._initialize(progress_callback)
        
        if self._ocr is None or not HAS_IMAGE_LIBS:
            return []
        
        try:
            # 确保图像是numpy数组
            if hasattr(image, 'size'):  # PIL Image
                image_array = np.array(image.convert('RGB'))
                if progress_callback:
                    progress_callback.update(f"OCR: 图片尺寸 {image.size}, 数组形状 {image_array.shape}")
            else:
                image_array = image
            
            if self._backend == "paddleocr":
                # PaddleOCR返回格式: [[[坐标], (文本, 置信度)], ...]
                # PaddleOCR 3.x 不再支持 cls 参数，角度分类在初始化时通过 use_angle_cls 控制
                if progress_callback:
                    progress_callback.update("OCR: 开始调用PaddleOCR识别...")
                
                result = self._ocr.ocr(image_array)
                
                if progress_callback:
                    if result is None:
                        progress_callback.update("OCR: PaddleOCR返回None")
                    elif not result:
                        progress_callback.update("OCR: PaddleOCR返回空列表")
                    elif not result[0]:
                        progress_callback.update("OCR: PaddleOCR返回空结果列表")
                    else:
                        progress_callback.update(f"OCR: PaddleOCR返回 {len(result[0])} 个结果")
                
                if result and result[0]:
                    results = []
                    # 按Y坐标排序（从上到下）
                    items_with_y = []
                    for item in result[0]:
                        try:
                            # 检查数据结构：item 应该是 [[坐标], (文本, 置信度)]
                            if len(item) >= 2 and isinstance(item[1], (tuple, list)) and len(item[1]) >= 2:
                                text = item[1][0] if isinstance(item[1][0], str) else str(item[1][0])
                                conf = float(item[1][1]) if len(item[1]) > 1 else 0.0
                                
                                # 计算Y坐标（使用边界框的中心或顶部）
                                bbox = item[0] if len(item) > 0 else None
                                y_pos = 0
                                if bbox and isinstance(bbox, (list, tuple)) and len(bbox) > 0:
                                    try:
                                        y_coords = [point[1] for point in bbox if len(point) >= 2]
                                        y_pos = min(y_coords) if y_coords else 0  # 使用顶部Y坐标
                                    except:
                                        pass
                                
                                items_with_y.append((text, conf, y_pos))
                                
                                # 流式回调：每识别到一个块就立即返回
                                if stream_callback:
                                    stream_callback(text, conf, y_pos)
                        except (IndexError, TypeError, ValueError) as e:
                            if progress_callback:
                                progress_callback.update(f"OCR: PaddleOCR结果解析错误: {e}")
                            print(f"PaddleOCR结果解析错误: {e}, item: {item}")
                            continue
                    
                    # 按Y坐标排序
                    items_with_y.sort(key=lambda x: x[2])
                    results = [(text, conf) for text, conf, _ in items_with_y]
                    
                    if progress_callback:
                        progress_callback.update(f"OCR: 成功解析 {len(results)} 个文本块")
                    
                    return results
                
                if progress_callback:
                    progress_callback.update("OCR: PaddleOCR未返回有效结果")
                return []
            elif self._backend == "easyocr":
                # EasyOCR返回格式: [([坐标], 文本, 置信度), ...]
                result = self._ocr.readtext(image_array)
                return [(item[1], item[2]) for item in result]
            elif self._backend == "tesseract":
                # Tesseract返回文本和置信度
                from PIL import Image as PILImage
                if isinstance(image_array, np.ndarray):
                    pil_image = PILImage.fromarray(image_array)
                else:
                    pil_image = image
                text = self._ocr.image_to_string(pil_image, lang='chi_sim+eng')
                data = self._ocr.image_to_data(pil_image, lang='chi_sim+eng', output_type=self._ocr.Output.DICT)
                results = []
                for i, conf in enumerate(data['conf']):
                    if int(conf) > 0:
                        text_item = data['text'][i].strip()
                        if text_item:
                            results.append((text_item, float(conf) / 100.0))
                return results
        except Exception as e:
            print(f"OCR提取错误: {e}")
            return []
        
        return []
    
    def detect_math_formulas(self, image, progress_callback=None) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
        """
        检测图像中的数学公式
        
        Args:
            image: PIL Image对象或numpy数组
            progress_callback: 可选的进度回调函数
            
        Returns:
            List of (latex_formula, confidence, bbox) tuples
        """
        self._initialize(progress_callback)
        
        if self._ocr is None or not HAS_IMAGE_LIBS:
            return []
        
        # 这里可以集成专门的数学公式识别模型
        # 例如：MathPix API、Nougat、或PaddleOCR的数学公式检测模块
        # 目前先返回空列表，后续可以扩展
        
        try:
            # 确保图像是numpy数组
            if hasattr(image, 'size'):  # PIL Image
                image_array = np.array(image)
            else:
                image_array = image
            
            # 使用PaddleOCR检测可能的公式区域
            if self._backend == "paddleocr":
                # PaddleOCR 3.x 不再支持 cls 参数
                result = self._ocr.ocr(image_array)
                formulas = []
                if result and result[0]:
                    for item in result[0]:
                        try:
                            # 检查数据结构
                            if len(item) < 2:
                                continue
                            
                            # 获取文本和置信度
                            if isinstance(item[1], (tuple, list)) and len(item[1]) >= 2:
                                text = item[1][0] if isinstance(item[1][0], str) else str(item[1][0])
                                conf = float(item[1][1]) if len(item[1]) > 1 else 0.0
                            else:
                                continue
                            
                            # 获取边界框
                            bbox = item[0] if len(item) > 0 and isinstance(item[0], (list, tuple)) else None
                            if not bbox:
                                continue
                            
                            # 简单的公式检测：包含数学符号的文本
                            math_indicators = ['=', '∑', '∫', '√', '≤', '≥', '≠', '±', '×', '÷', 
                                             'α', 'β', 'γ', 'π', 'θ', 'λ', 'μ', 'σ', '∞', '∂']
                            if any(indicator in text for indicator in math_indicators):
                                # 尝试转换为LaTeX（简化版）
                                latex = self._text_to_latex(text)
                                if latex:
                                    # 计算边界框
                                    try:
                                        x_coords = [point[0] for point in bbox if len(point) >= 2]
                                        y_coords = [point[1] for point in bbox if len(point) >= 2]
                                        if x_coords and y_coords:
                                            bbox_tuple = (
                                                int(min(x_coords)),
                                                int(min(y_coords)),
                                                int(max(x_coords)),
                                                int(max(y_coords))
                                            )
                                            formulas.append((latex, conf, bbox_tuple))
                                    except (IndexError, TypeError, ValueError) as e:
                                        print(f"边界框计算错误: {e}, bbox: {bbox}")
                                        continue
                        except (IndexError, TypeError, ValueError) as e:
                            print(f"PaddleOCR公式检测结果解析错误: {e}, item: {item}")
                            continue
                return formulas
        except Exception as e:
            print(f"公式检测错误: {e}")
        
        return []
    
    def _text_to_latex(self, text: str) -> Optional[str]:
        """
        将文本转换为LaTeX格式（简化版）
        实际应用中可以使用更专业的数学公式识别模型
        """
        # 简单的转换规则
        text = text.strip()
        if not text:
            return None
        
        # 如果已经是LaTeX格式，直接返回
        if text.startswith('$') or '\\' in text:
            return text
        
        # 简单的数学表达式检测
        # 这里可以集成更专业的模型，如MathPix API
        return text


class MathFormulaRecognizer:
    """专门的数学公式识别器"""
    
    def __init__(self):
        self._initialized = False
        self._model = None
    
    def _initialize(self):
        """初始化数学公式识别模型"""
        if self._initialized:
            return
        
        # 可以集成以下模型之一：
        # 1. Nougat (Meta的学术论文OCR模型)
        # 2. MathPix API
        # 3. PaddleOCR的数学公式模块
        # 4. TrOCR + 数学公式检测
        
        try:
            # 尝试使用Nougat（需要安装transformers）
            # from transformers import NougatProcessor, NougatModel
            # self._model = ...
            pass
        except ImportError:
            print("Warning: 数学公式识别模型未安装")
            print("可选方案: pip install transformers (用于Nougat)")
            print("或使用 MathPix API (需要API密钥)")
        
        self._initialized = True
    
    def recognize(self, image: Image.Image) -> Optional[str]:
        """
        识别图像中的数学公式，返回LaTeX格式
        
        Args:
            image: PIL Image对象
            
        Returns:
            LaTeX格式的公式字符串，如果无法识别则返回None
        """
        self._initialize()
        
        if self._model is None:
            return None
        
        # 实现数学公式识别逻辑
        # 返回LaTeX格式的公式
        return None
