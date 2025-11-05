from __future__ import annotations

from src.components import clamp_baseline


class TestClampBaseline:
    def test_clamp_y_near_top(self):
        # page_h=100, margin=2, font_size=10 -> ascent=8, descent=2
        # y_max = 100 - 2 - 8 = 90
        x, y = clamp_baseline(x=10, y_baseline=99, page_width=200, page_height=100, font_size=10, margin=2)
        assert y == 90
        assert x == 10

    def test_clamp_y_near_bottom(self):
        # y_min = margin + descent = 2 + 2 = 4
        x, y = clamp_baseline(x=10, y_baseline=1, page_width=200, page_height=100, font_size=10, margin=2)
        assert y == 4
        assert x == 10

    def test_clamp_x_left_and_right(self):
        # x 左侧越界
        x, y = clamp_baseline(x=-5, y_baseline=50, page_width=50, page_height=100, font_size=10, margin=2)
        assert x == 2
        # x 右侧越界
        x2, y2 = clamp_baseline(x=60, y_baseline=50, page_width=50, page_height=100, font_size=10, margin=2)
        assert x2 == 48

    def test_degenerate_case_fallback_to_regular_clamp(self):
        # 极端：字体很大导致 y_min > y_max，触发退化为常规钳制 [margin, page_h - margin]
        x, y = clamp_baseline(x=10, y_baseline=100, page_width=100, page_height=20, font_size=50, margin=2)
        assert y == 18  # page_h - margin
        assert x == 10


