"""
文件路径：tests/test_page_range_param.py

用例目的：验证页范围参数贯通（CLI/GUI/处理器已实现），确保：
- pages="all" 命中全部存在的关键词
- pages="1" 仅命中第一页的关键词
- pages="2" 仅命中第二页的关键词
- pages="1,2" 等价于 all（在本两页场景）
- pages="999" 无效页选择将回退为 all（根据实现约定：空解析回退为全页）

依赖：
- 仅使用 src/pdf_processor.PDFProcessor 与 ReportLab 生成测试 PDF
- 不依赖外部示例文件，测试内自建两页 PDF，分别放置不同关键词
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

from src.pdf_processor import PDFProcessor
from src.variables import PATH_TEMP_DIR


def _build_two_page_pdf(path: Path) -> None:
    """生成一个两页的测试 PDF：

    - 第 1 页包含关键词 "K1:"（位于 (72, 800)）
    - 第 2 页包含关键词 "K2:"（位于 (72, 800)）
    """
    from reportlab.pdfgen import canvas  # 延迟导入以加快测试收敛

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.setPageSize((595.28, 841.89))  # A4 portrait
    c.setFont("Helvetica", 12)

    # Page 1
    c.drawString(72, 800, "K1:")
    c.showPage()

    # Page 2
    c.setFont("Helvetica", 12)
    c.drawString(72, 800, "K2:")
    c.save()


@pytest.mark.parametrize(
    "pages,expected_matched",
    [
        ("all", 2),
        ("1", 1),
        ("2", 1),
        ("1,2", 2),
        ("999", 2),  # 无效选择应回退为全页
    ],
)
def test_page_range_selection_behaviour(tmp_path: Path, pages: str, expected_matched: int) -> None:
    # 1) 构建输入 PDF（两页）
    input_pdf = tmp_path / "page_range_fixture.pdf"
    _build_two_page_pdf(input_pdf)

    # 2) 构建输入数据：两个关键词分别在不同页
    data: Dict[str, str] = {"K1:": "V1", "K2:": "V2"}

    # 3) 执行填充（使用 reportlab 路线以保证环境稳定）
    processor = PDFProcessor()
    out = PATH_TEMP_DIR / f"test_page_range_{pages.replace(',', '_').replace('-', '_')}.pdf"
    result_path = processor.fill_by_keywords(
        input_pdf,
        data,
        per_key_overrides={},
        output_path=out,
        pages=pages,
        fuzzy_threshold=0.95,
        engine="reportlab",
    )

    assert result_path.exists(), "输出文件未生成"

    # 4) 断言匹配统计
    stats = getattr(processor, "last_fill_stats", None)
    assert isinstance(stats, dict), "未产生统计信息"
    assert int(stats.get("matched", -1)) == expected_matched
    assert int(stats.get("total", -1)) == 2
    assert int(stats.get("missing_count", -1)) == 2 - expected_matched


