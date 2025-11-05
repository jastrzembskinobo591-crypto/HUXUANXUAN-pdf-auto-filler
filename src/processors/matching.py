"""
文件路径：src/processors/matching.py

说明：从 `pdf_processor` 拆分的匹配相关工具：文本归一化、滑窗匹配、字符包围盒合成。
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import List, Optional, Tuple


def normalize_text(s: str) -> str:
    """规范化字符串：全角冒号替换为半角、去除空白，便于模糊匹配。"""
    return (
        s.replace("：", ":")
        .replace("\u3000", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def best_fuzzy_window(chars: List[dict], keyword: str, threshold: float) -> Optional[Tuple[int, int]]:
    """在字符序列上滑窗，寻找与关键词最相近的子串索引区间。

    返回 (start_idx, end_idx) 若找到最佳且 >= 阈值，否则 None。
    """
    norm_keyword = normalize_text(keyword)
    target_len = len(norm_keyword)
    if target_len == 0 or not chars:
        return None

    texts = [normalize_text(c.get("text", "")) for c in chars]

    best = (0.0, None)  # (score, (i, j))
    for i in range(0, len(texts) - target_len + 1):
        window = "".join(texts[i : i + target_len])
        score = SequenceMatcher(a=norm_keyword, b=window).ratio()
        if score > best[0]:
            best = (score, (i, i + target_len))

    if best[1] is not None and best[0] >= threshold:
        return best[1]
    return None


def bbox_of_chars(chars: List[dict], start: int, end: int) -> Tuple[float, float, float, float]:
    """根据字符起止索引计算包围盒 (x0, y0, x1, y1)（pdfplumber 坐标）。"""
    xs0 = [chars[i]["x0"] for i in range(start, end)]
    xs1 = [chars[i]["x1"] for i in range(start, end)]
    tops = [chars[i]["top"] for i in range(start, end)]
    bottoms = [chars[i]["bottom"] for i in range(start, end)]
    return (min(xs0), min(tops), max(xs1), max(bottoms))


__all__ = ["normalize_text", "best_fuzzy_window", "bbox_of_chars"]



