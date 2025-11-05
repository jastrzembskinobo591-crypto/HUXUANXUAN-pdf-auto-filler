from __future__ import annotations

from pathlib import Path

from src.data_handler import load_templates_index, infer_template_id_from_filename


def test_load_templates_index_old_structure(tmp_path):
    p = tmp_path / "templates.json"
    p.write_text(
        '{"default": "config/keywords.json", "bank_b": "config/keywords_bank_b.json"}',
        encoding="utf-8",
    )
    mapping = load_templates_index(index_path=p)
    assert mapping["default"].endswith("config/keywords.json")
    assert mapping["bank_b"].endswith("config/keywords_bank_b.json")


def test_infer_template_id_old_structure_by_filename(tmp_path):
    p = tmp_path / "templates.json"
    p.write_text(
        '{"default": "config/keywords.json", "bank_b": "config/keywords_bank_b.json"}',
        encoding="utf-8",
    )
    # 文件名包含 bank_b，应该匹配 bank_b
    tid = infer_template_id_from_filename(Path("examples/bank_b_contract.pdf"), index_path=p)
    assert tid == "bank_b"


def test_infer_template_id_new_structure_with_patterns(tmp_path):
    p = tmp_path / "templates.json"
    p.write_text(
        '{\n'
        '  "default": {"path": "config/keywords.json", "match_patterns": ["default"]},\n'
        '  "bank_b": {"path": "config/keywords_bank_b.json", "match_patterns": ["合同B", "bank_b"]}\n'
        '}',
        encoding="utf-8",
    )
    # 文件名包含中文匹配词“合同B”
    tid = infer_template_id_from_filename(Path("客户_合同B_v1.pdf"), index_path=p)
    assert tid == "bank_b"


