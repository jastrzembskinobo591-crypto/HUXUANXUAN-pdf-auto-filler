"""
文件路径：tests/test_alias_matching.py

用例目的：验证“别名解析与匹配”工作流——输入别名 + 配置 aliases + 规范名 的合并候选。

覆盖场景：
- 输入使用配置中的别名（应命中）
- 输入使用规范名（应命中）
- 输入键自身包含别名分隔符（应命中）
- 输入/配置均无法命中（应记为 missing）

说明：
- 仅依赖 ReportLab 生成测试 PDF，避免外部资源。
- 通过 per_key_overrides 直接传入已规范化的 aliases 列表，避免读写配置文件。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

from src.pdf_processor import PDFProcessor
from src.variables import PATH_TEMP_DIR


def _build_single_page_with_canon(path: Path, text: str = "CANON:") -> None:
    """生成单页 PDF，页面上包含给定规范关键词。"""
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.setPageSize((595.28, 841.89))  # A4
    c.setFont("Helvetica", 12)
    c.drawString(72, 800, text)
    c.save()


@pytest.mark.parametrize(
    "input_key,expected_matched,expected_missing",
    [
        ("AL1:", 1, 0),  # 输入别名命中
        ("CANON:", 1, 0),  # 输入即规范名
        ("AL2:|OTHER:", 1, 0),  # 输入包含别名分隔符
        ("MISSING:", 0, 1),  # 无法命中
    ],
)
def test_alias_matching(tmp_path: Path, input_key: str, expected_matched: int, expected_missing: int) -> None:
    # 1) 准备输入 PDF（仅包含规范名 CANON:）
    input_pdf = tmp_path / "alias_fixture.pdf"
    _build_single_page_with_canon(input_pdf, text="CANON:")

    # 2) 覆盖：为规范名提供 aliases（含自身 + 两个别名）
    per_key_overrides: Dict[str, dict] = {
        "CANON:": {"page": 0, "offset_x": 50.0, "aliases": ["CANON:", "AL1:", "AL2:"]}
    }

    # 3) 构建待填充数据（仅一个键，键名称由参数化提供）
    data: Dict[str, str] = {input_key: "VALUE"}

    # 4) 执行填充（ReportLab 路线 + 提升阈值以避免误匹配）
    processor = PDFProcessor()
    out = PATH_TEMP_DIR / f"test_alias_{input_key.replace('|', '_').replace(':', '')}.pdf"
    result_path = processor.fill_by_keywords(
        input_pdf,
        data,
        per_key_overrides=per_key_overrides,
        output_path=out,
        fuzzy_threshold=0.95,
        engine="reportlab",
    )

    assert result_path.exists(), "输出文件未生成"

    # 5) 断言统计
    stats = getattr(processor, "last_fill_stats", None)
    assert isinstance(stats, dict), "未产生统计信息"
    assert int(stats.get("matched", -1)) == expected_matched
    assert int(stats.get("missing_count", -1)) == expected_missing


