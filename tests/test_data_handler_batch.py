from __future__ import annotations

from pathlib import Path

import pytest

from src.data_handler import load_batch_json, load_batch_csv


def test_load_batch_json_examples():
    path = Path("examples/batch.json")
    rows = load_batch_json(path)
    assert isinstance(rows, list) and len(rows) == 2
    assert rows[0]["身份证号："].isdigit()
    assert "企业名称：" in rows[0]


def test_load_batch_json_with_bom(tmp_path):
    # 写入带 BOM 的 JSON 内容
    bom_json = "\ufeff[ {\n  \"身份证号：\": \"1\", \"企业名称：\": \"X\"\n} ]"
    p = tmp_path / "bom.json"
    p.write_text(bom_json, encoding="utf-8")
    rows = load_batch_json(p)
    assert rows == [{"身份证号：": "1", "企业名称：": "X"}]


def test_load_batch_csv_examples():
    path = Path("examples/batch.csv")
    rows = load_batch_csv(path)
    assert isinstance(rows, list) and len(rows) == 2
    assert rows[0]["身份证号："].isdigit()
    assert rows[1]["企业名称："]


