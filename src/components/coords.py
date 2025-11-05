"""
文件路径：src/components/coords.py

说明：坐标计算相关通用函数，从包入口拆分而来。
"""

from __future__ import annotations

from typing import Tuple

from ..variables import CONST_CLAMP_MARGIN_DEFAULT


def adjust_coords(x: float, y: float, offset_x: float, offset_y: float) -> Tuple[float, float]:
    """对坐标应用偏移（ReportLab/pdfplumber 坐标系默认左下角为原点）。

    参数：
        x: 原始 X 坐标。
        y: 原始 Y 坐标。
        offset_x: X 方向偏移量（向右为正）。
        offset_y: Y 方向偏移量（向上为正）。

    返回：
        偏移后的 (x, y)。
    """
    return (x + offset_x, y + offset_y)


def clamp_coords(
    x: float,
    y: float,
    page_width: float,
    page_height: float,
    margin: float = 0.0,
) -> Tuple[float, float]:
    """将坐标限制在页面范围内，避免写出页面边界。

    参数：
        x, y: 输入坐标。
        page_width, page_height: 页面宽高（pt）。
        margin: 允许的内边距。
    返回：
        (clamped_x, clamped_y)
    """
    clamped_x = max(margin, min(page_width - margin, x))
    clamped_y = max(margin, min(page_height - margin, y))
    return clamped_x, clamped_y


def clamp_baseline(
    x: float,
    y_baseline: float,
    page_width: float,
    page_height: float,
    font_size: float,
    margin: float = CONST_CLAMP_MARGIN_DEFAULT,
    ascent_ratio: float = 0.8,
    descent_ratio: float = 0.2,
) -> Tuple[float, float]:
    """基线感知的钳制：保证文本不因上升/下降而被整行裁剪。

    说明：
    - 三路径都以基线 y 为参考；若基线离顶部过近，上升线会越界被裁剪；
      离底部过近则下降线越界。本函数在 y 方向考虑 ascent/descender 进行钳制。
    """
    # X 仍按常规钳制
    x_clamped = max(margin, min(page_width - margin, x))

    ascent = max(0.0, float(font_size) * float(ascent_ratio))
    descent = max(0.0, float(font_size) * float(descent_ratio))
    y_min = margin + descent
    y_max = page_height - margin - ascent
    if y_min > y_max:
        # 极端情况：页面很小或字体很大时，退化为常规钳制
        y_min, y_max = margin, page_height - margin
    y_clamped = max(y_min, min(y_max, y_baseline))
    return x_clamped, y_clamped


def right_of_bbox(
    bbox: Tuple[float, float, float, float],
    offset_x: float,
    offset_y: float,
) -> Tuple[float, float]:
    """返回位于 bbox 右侧的填充锚点坐标。

    参数：
        bbox: (x0, y0, x1, y1) 矩形框。
        offset_x: 右侧 X 偏移。
        offset_y: Y 偏移。
    返回：
        (x1 + offset_x, y0 + offset_y)
    """
    x0, y0, x1, _ = bbox
    return x1 + offset_x, y0 + offset_y


def right_of_bbox_baseline(
    bbox: Tuple[float, float, float, float],
    offset_x: float,
    offset_y: float,
) -> Tuple[float, float]:
    """返回以文本基线（bottom）为基准的右侧锚点坐标。

    说明：pdfplumber 的 bbox 为 (x0, top, x1, bottom)。与 ReportLab 配合时，
    使用 bottom 作为 y 基线可更好地与原标签文字对齐。
    """
    x0, _, x1, y1 = bbox
    return x1 + offset_x, y1 + offset_y


__all__ = [
    "adjust_coords",
    "clamp_coords",
    "clamp_baseline",
    "right_of_bbox",
    "right_of_bbox_baseline",
]



