"""
文件路径：src/components/page.py

说明：页面相关工具函数（页选择解析）从包入口拆分而来。
"""

from __future__ import annotations

import logging
from typing import List


def parse_page_selection(selection: str, total_pages: int, one_based: bool = True) -> List[int]:
    """解析页选择字符串，返回去重且排序的 0 基页索引列表。

    支持的格式：
    - "all"：全部页面
    - "1,3-5,8"：逗号分隔，支持范围（闭区间）与单页
    """
    logger = logging.getLogger(__name__)
    if not selection:
        return []

    sel = selection.strip().lower()
    if sel == "all":
        return list(range(total_pages))

    result: List[int] = []

    def _add(idx: int) -> None:
        if one_based:
            idx -= 1
        if idx < 0 or idx >= total_pages:
            logger.warning("页索引越界，已忽略：%s / total=%s", idx, total_pages)
            return
        result.append(idx)

    for part in sel.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start_i = int(start_s)
                end_i = int(end_s)
            except ValueError:
                logger.warning("无法解析页范围：%s，已忽略", part)
                continue
            if start_i > end_i:
                start_i, end_i = end_i, start_i
            for i in range(start_i, end_i + 1):
                _add(i)
        else:
            try:
                _add(int(part))
            except ValueError:
                logger.warning("无法解析页索引：%s，已忽略", part)
                continue

    return sorted(set(result))


__all__ = ["parse_page_selection"]



