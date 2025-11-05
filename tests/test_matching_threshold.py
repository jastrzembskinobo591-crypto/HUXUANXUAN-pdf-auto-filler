from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "thr, expected_missing",
    [
        (0.60, 0),  # 低阈值：应命中“企业名：”≈“企业名称：”
        (0.95, 1),  # 高阈值：应未命中“企业名：”
    ],
)
def test_fill_by_keywords_respects_fuzzy_threshold(thr: float, expected_missing: int):
    from pathlib import Path

    from src.pdf_processor import PDFProcessor
    from src.data_handler import load_keywords_config
    from src.variables import PATH_EXAMPLES_DIR

    input_pdf = PATH_EXAMPLES_DIR / "blank_contract.pdf"
    assert input_pdf.exists(), "示例 PDF 不存在，请先运行 --make-example 生成"

    processor = PDFProcessor()
    overrides = load_keywords_config(None)

    # 使用近似关键词“企业名：”与严格匹配“身份证号：”
    pairs = {"企业名：": "某某科技", "身份证号：": "123456789012345678"}

    out = processor.fill_by_keywords(
        input_pdf,
        pairs,
        per_key_overrides=overrides,
        output_path=None,
        pages=None,
        fuzzy_threshold=thr,
        engine="reportlab",  # 使用稳定的 overlay 合成路径，避免环境差异
    )

    assert isinstance(out, Path)
    stats = getattr(processor, "last_fill_stats", None)
    assert isinstance(stats, dict)
    assert int(stats.get("missing_count", -1)) == expected_missing


