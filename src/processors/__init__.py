"""
文件路径：src/processors/__init__.py

说明：
- 最小重构阶段的占位包，保持对外 API 不变；
- 后续将把 `src/pdf_processor.py` 的实现按职责逐步迁移至：
  - matching.py（归一化/滑窗/别名候选）
  - layout.py（换行/基线与贴边钳制）
  - engines/{pymupdf.py, reportlab.py, raster.py}（三引擎绘制）
"""

from typing import List

__all__: List[str] = []


