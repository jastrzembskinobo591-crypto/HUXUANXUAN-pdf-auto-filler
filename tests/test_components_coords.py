from src.components import clamp_coords


def test_clamp_basic_center():
    x, y = clamp_coords(50, 60, page_width=200, page_height=100, margin=2)
    assert (x, y) == (50, 60)


def test_clamp_left_bottom_margin():
    x, y = clamp_coords(-10, -5, page_width=200, page_height=100, margin=2)
    assert (x, y) == (2, 2)


def test_clamp_right_top_margin():
    x, y = clamp_coords(500, 500, page_width=200, page_height=100, margin=2)
    assert (x, y) == (198, 98)


