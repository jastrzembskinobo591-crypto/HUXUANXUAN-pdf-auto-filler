from __future__ import annotations

"""
pytest 全局配置：将项目根目录加入 sys.path，确保 `from src...` 可被导入。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)


