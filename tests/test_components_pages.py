from pathlib import Path

import pytest

from src.components import parse_page_selection


class TestParsePageSelection:
    def test_all_pages(self):
        assert parse_page_selection("all", total_pages=5, one_based=True) == [0, 1, 2, 3, 4]

    def test_single_and_ranges(self):
        # 1 基输入："1,3-5" -> 0,2,3,4
        assert parse_page_selection("1,3-5", total_pages=6, one_based=True) == [0, 2, 3, 4]

    def test_spaces_and_uppercase(self):
        assert parse_page_selection("  All  ", total_pages=3, one_based=True) == [0, 1, 2]
        assert parse_page_selection("1 , 2-3 ", total_pages=3, one_based=True) == [0, 1, 2]

    def test_out_of_range_filtered(self, caplog):
        res = parse_page_selection("0,1,99", total_pages=2, one_based=True)
        # 1 基：0 会被转成 -1，99 -> 98 越界，两者被过滤，仅保留 1 -> 0
        assert res == [0]

    def test_one_based_false(self):
        # 0 基输入：0,2-3 -> 0,2,3
        assert parse_page_selection("0,2-3", total_pages=4, one_based=False) == [0, 2, 3]

    def test_invalid_parts_ignored(self):
        # 非法片段被忽略，合法片段保留
        assert parse_page_selection("x,1-*,2", total_pages=3, one_based=True) == [1]
