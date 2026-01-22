# core/image_splitter.py
"""
Image splitter for PDF pages.
Split page image into paragraph-level regions.
"""

from typing import List, Tuple
from PIL import Image
import numpy as np

try:
    HAS_IMAGE_LIBS = True
except ImportError:
    HAS_IMAGE_LIBS = False
    np = None


class ImageSplitter:
    """
    Split PDF page image into paragraph images.
    """

    def __init__(self):
        pass

    def split_into_lines(
        self,
        image: Image.Image,
        ocr_engine=None
    ) -> List[Tuple[Image.Image, int, int]]:
        """
        Split page into paragraph regions.

        Returns:
            List of (paragraph_image, y_start, y_end)
        """
        if not HAS_IMAGE_LIBS:
            return []

        if ocr_engine and hasattr(ocr_engine, "_ocr") and ocr_engine._ocr:
            try:
                return self._split_by_ocr_paragraph(image, ocr_engine)
            except Exception as e:
                print(f"OCR paragraph split failed: {e}")

        # fallback
        return [(image, 0, image.size[1])]

    # --------------------------------------------------
    # Core paragraph algorithm
    # --------------------------------------------------

    def _split_by_ocr_paragraph(
        self,
        image: Image.Image,
        ocr_engine
    ) -> List[Tuple[Image.Image, int, int]]:
        """
        Paragraph-aware OCR splitting.
        """
        img_array = np.array(image.convert("RGB"))
        ocr_result = ocr_engine._ocr.ocr(img_array)

        if not ocr_result or not ocr_result[0]:
            return [(image, 0, image.size[1])]

        lines = []
        for item in ocr_result[0]:
            bbox = item[0]
            if not bbox:
                continue

            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]

            lines.append(
                {
                    "y_min": min(ys),
                    "y_max": max(ys),
                    "x_min": min(xs),
                    "x_max": max(xs),
                    "height": max(ys) - min(ys),
                }
            )

        if len(lines) <= 1:
            return [(image, 0, image.size[1])]

        # sort by vertical position
        lines.sort(key=lambda x: x["y_min"])

        # compute median line gap
        gaps = [
            lines[i + 1]["y_min"] - lines[i]["y_max"]
            for i in range(len(lines) - 1)
        ]
        median_gap = np.median([g for g in gaps if g > 0]) if gaps else 0

        paragraphs: List[Tuple[int, int]] = []

        cur_start = lines[0]["y_min"]
        cur_end = lines[0]["y_max"]

        for i in range(len(lines) - 1):
            l1 = lines[i]
            l2 = lines[i + 1]

            vertical_gap = l2["y_min"] - l1["y_max"]
            indent_diff = abs(l2["x_min"] - l1["x_min"])

            overlap_width = min(l1["x_max"], l2["x_max"]) - max(
                l1["x_min"], l2["x_min"]
            )
            union_width = max(l1["x_max"], l2["x_max"]) - min(
                l1["x_min"], l2["x_min"]
            )
            overlap_ratio = (
                overlap_width / union_width if union_width > 0 else 0
            )

            same_paragraph = (
                vertical_gap < max(1.5 * median_gap, 8)
                and indent_diff < 40
                and overlap_ratio > 0.6
            )

            if same_paragraph:
                cur_end = l2["y_max"]
            else:
                paragraphs.append((cur_start, cur_end))
                cur_start = l2["y_min"]
                cur_end = l2["y_max"]

        paragraphs.append((cur_start, cur_end))

        # crop paragraph images
        width, height = image.size
        results = []

        for y_start, y_end in paragraphs:
            y0 = max(0, int(y_start) - 5)
            y1 = min(height, int(y_end) + 5)

            if y1 - y0 > 20:
                para_img = image.crop((0, y0, width, y1))
                results.append((para_img, y0, y1))

        return results