"""
文件路径：src/components/text.py

说明：文本度量、分割与别名解析相关工具函数，从包入口拆分而来。
"""

from __future__ import annotations

from typing import List

from ..variables import CONST_ALIAS_SEPARATOR


def estimate_text_width(
    text: str,
    font_size: float,
    char_width_ratio: float = 0.6,
) -> float:
    """估算文本宽度（简化版）。

    - 中文按 font_size 计算；ASCII 按 font_size * char_width_ratio。
    """
    if not text:
        return 0.0
    width = 0.0
    for char in text:
        if ord(char) > 127:
            width += font_size
        else:
            width += font_size * char_width_ratio
    return width


def split_text_by_width(
    text: str,
    max_width: float,
    font_size: float,
    char_width_ratio: float = 0.6,
) -> List[str]:
    """按最大宽度分割文本为多行（贪心策略）。"""
    if not text or max_width <= 0:
        return [text] if text else []

    lines: List[str] = []
    current_line = ""
    current_width = 0.0

    for char in text:
        char_w = font_size if ord(char) > 127 else font_size * char_width_ratio
        if current_width + char_w <= max_width:
            current_line += char
            current_width += char_w
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
            current_width = char_w

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


def split_aliases(keyword: str, sep: str = CONST_ALIAS_SEPARATOR) -> List[str]:
    """将包含别名语法的关键词按分隔符拆分并清洗。"""
    if keyword is None:
        return []
    raw = str(keyword)
    parts = [raw] if sep not in raw else raw.split(sep)
    seen: set[str] = set()
    result: List[str] = []
    for p in parts:
        t = p.strip()
        if not t:
            continue
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result if result else [str(keyword).strip()]


__all__ = [
    "estimate_text_width",
    "split_text_by_width",
    "split_aliases",
]



