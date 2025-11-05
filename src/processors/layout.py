"""
文件路径：src/processors/layout.py

说明：从 `PDFProcessor` 拆分的布局相关函数。
"""

from __future__ import annotations

from typing import List, Optional

from reportlab.pdfbase import pdfmetrics


def wrap_text_lines(
    font_name: str,
    font_size: int,
    text: str,
    max_width: Optional[float],
) -> List[str]:
    """按最大行宽将文本分行（与原处理器行为一致）。

    - 若 max_width 为空或 <=0，则不换行，保持原字符串（仅按原始换行符拆分）。
    - 使用 ReportLab 字体度量（pdfmetrics.stringWidth）估计宽度；
      即使在 PyMuPDF / Raster 路径中也沿用该度量以保持一致性。
    """
    if text is None:
        return []
    raw_lines = str(text).splitlines() or [""]
    if max_width is None or max_width <= 0:
        return [ln for ln in raw_lines]

    wrapped: List[str] = []
    for raw in raw_lines:
        current = ""
        for ch in raw:
            trial = current + ch
            try:
                w = pdfmetrics.stringWidth(trial, font_name, font_size)
            except Exception:
                # 度量失败时回退：按字符数量粗略截断
                w = len(trial) * float(font_size) * 0.6
            if w <= max_width or current == "":
                current = trial
            else:
                wrapped.append(current)
                current = ch
        wrapped.append(current)
    return wrapped


__all__ = ["wrap_text_lines"]



