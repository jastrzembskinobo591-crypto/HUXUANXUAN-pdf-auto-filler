from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.components import FileHandler, get_logger  # type: ignore
from src.pdf_processor import PDFProcessor  # type: ignore
from src.variables import (  # type: ignore
    PATH_DEFAULT_INPUT_PDF,
    PATH_OUTPUT_DIR,
)


def main() -> None:
    logger = get_logger(__name__)
    FileHandler.ensure_project_dirs()

    input_pdf = PATH_DEFAULT_INPUT_PDF
    if not input_pdf.exists():
        raise FileNotFoundError(f"未找到示例 PDF：{input_pdf}")

    # 测试数据
    kv = {"身份证号：": "12345678901234567890", "企业名称：": "哇棒某某科技有限公司"}

    proc = PDFProcessor()

    # 1) 开启贴边保护（边距=2）
    out1 = FileHandler.timestamped_output_path(input_pdf, prefix="clamp_test")
    proc.fill_by_keywords(
        input_pdf,
        kv,
        per_key_overrides=None,
        output_path=out1,
        engine="pymupdf",
        enable_clamp=True,
        clamp_margin=2.0,
    )
    size1 = out1.stat().st_size
    logger.info("开启贴边保护输出：%s (%d bytes)", out1, size1)

    # 2) 关闭贴边保护（边距=0）
    out2 = FileHandler.timestamped_output_path(input_pdf, prefix="clamp_off")
    proc.fill_by_keywords(
        input_pdf,
        kv,
        per_key_overrides=None,
        output_path=out2,
        engine="pymupdf",
        enable_clamp=False,
        clamp_margin=0.0,
    )
    size2 = out2.stat().st_size
    logger.info("关闭贴边保护输出：%s (%d bytes)", out2, size2)

    print(json.dumps({
        "clamp_on": str(out1),
        "clamp_on_size": size1,
        "clamp_off": str(out2),
        "clamp_off_size": size2,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()


