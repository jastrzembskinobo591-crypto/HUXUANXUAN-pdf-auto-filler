from __future__ import annotations

import math

from src.components import estimate_text_width, split_text_by_width


class TestTextWidthEstimation:
    def test_empty_text_width_is_zero(self):
        assert estimate_text_width("", 12) == 0.0

    def test_mixed_cjk_ascii_width(self):
        # "测试ABC" -> 2*CJK*12 + 3*ASCII*12*0.6 = 24 + 21.6 = 45.6
        w = estimate_text_width("测试ABC", font_size=12, char_width_ratio=0.6)
        assert math.isclose(w, 45.6, rel_tol=1e-6, abs_tol=1e-6)


class TestSplitTextByWidth:
    def test_split_cjk_exact_two_chars_per_line(self):
        # 每行最大 24pt，中文字符宽 ~ font_size=12 -> 正好每行 2 个
        lines = split_text_by_width("测试文本", max_width=24, font_size=12)
        assert lines == ["测试", "文本"]

    def test_split_ascii_fixed_ratio(self):
        # ASCII 宽度 0.5*font_size=6pt，max_width=18 -> 每行 3 个
        lines = split_text_by_width("ABCD", max_width=18, font_size=12, char_width_ratio=0.5)
        assert lines == ["ABC", "D"]

    def test_char_wider_than_line(self):
        # 单个中文字符宽 12pt，大于 max_width=10 -> 单字符独占一行
        lines = split_text_by_width("测试", max_width=10, font_size=12)
        assert lines == ["测", "试"]

    def test_empty_returns_empty_list(self):
        assert split_text_by_width("", max_width=30, font_size=12) == []


