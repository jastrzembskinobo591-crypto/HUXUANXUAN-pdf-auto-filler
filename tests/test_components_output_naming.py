from __future__ import annotations

from pathlib import Path

import pytest

from src.components import FileHandler
from src.variables import (
    PATH_OUTPUT_DIR,
    CONST_DEFAULT_OUTPUT_SUFFIX,
    CONST_INDEX_PAD_WIDTH_DEFAULT,
)


def test_timestamped_output_uses_input_stem_when_no_prefix(monkeypatch):
    # 固定时间戳，避免不稳定性
    monkeypatch.setattr("time.strftime", lambda fmt: "20250101_120000")
    out = FileHandler.timestamped_output_path(Path("/tmp/invoice.pdf"))
    assert out.parent == PATH_OUTPUT_DIR
    assert out.name == f"invoice_20250101_120000{CONST_DEFAULT_OUTPUT_SUFFIX}"


def test_timestamped_output_prefix_override(monkeypatch):
    monkeypatch.setattr("time.strftime", lambda fmt: "20250101_120000")
    out = FileHandler.timestamped_output_path(Path("/tmp/invoice.pdf"), prefix="mydoc")
    assert out.parent == PATH_OUTPUT_DIR
    assert out.name == f"mydoc_20250101_120000{CONST_DEFAULT_OUTPUT_SUFFIX}"


def test_indexed_output_default_pad(monkeypatch):
    monkeypatch.setattr("time.strftime", lambda fmt: "20250101_120000")
    out = FileHandler.indexed_output_path(Path("/tmp/contract.pdf"), index=1)
    assert out.parent == PATH_OUTPUT_DIR
    assert out.name == f"contract_20250101_120000_{str(1).zfill(CONST_INDEX_PAD_WIDTH_DEFAULT)}{CONST_DEFAULT_OUTPUT_SUFFIX}"


def test_indexed_output_with_prefix_and_custom_pad(monkeypatch):
    monkeypatch.setattr("time.strftime", lambda fmt: "20250101_120000")
    out = FileHandler.indexed_output_path(Path("/tmp/contract.pdf"), index=5, pad=2, prefix="rpt")
    assert out.parent == PATH_OUTPUT_DIR
    assert out.name == f"rpt_20250101_120000_{str(5).zfill(2)}{CONST_DEFAULT_OUTPUT_SUFFIX}"


