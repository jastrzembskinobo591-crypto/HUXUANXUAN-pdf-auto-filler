from __future__ import annotations

import pytest


def _safe_create_app():
    try:
        from src.ui import PdfFillerApp

        app = PdfFillerApp()
        return app
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Tk/GUI 不可用，跳过 GUI 测试：{exc}")


def test_gui_missing_count_updates_on_high_threshold(monkeypatch):
    # 屏蔽所有消息框，避免阻塞 CI
    import tkinter.messagebox as mb

    for name in ("showinfo", "showwarning", "showerror"):
        if hasattr(mb, name):
            monkeypatch.setattr(mb, name, lambda *a, **k: None)

    app = _safe_create_app()
    try:
        # 切换到专家模式并设置高阈值
        from src.variables import CONST_UI_MODE_EXPERT

        app.ui_mode_var.set(CONST_UI_MODE_EXPERT)
        app._apply_ui_mode_settings()
        app.option_fuzzy_threshold_var.set("0.95")

        # 确保字段包含“企业名：”与“身份证号：”
        # 清空后按需添加
        for r in list(getattr(app, "field_rows", [])):
            r.frame.destroy()
        app.field_rows.clear()
        app._add_field_row("身份证号：", "123456789012345678")
        app._add_field_row("企业名：", "某某科技")

        # 执行
        app._on_execute_fill()

        # 断言“未找到关键词：1”
        assert app.var_missing.get().startswith("未找到关键词：")
        val = app.var_missing.get().split("：")[-1].strip()
        assert val.startswith("1")  # 允许后缀含中文
    finally:
        app.destroy()


def test_gui_missing_count_low_threshold(monkeypatch):
    # 屏蔽消息框
    import tkinter.messagebox as mb

    for name in ("showinfo", "showwarning", "showerror"):
        if hasattr(mb, name):
            monkeypatch.setattr(mb, name, lambda *a, **k: None)

    app = _safe_create_app()
    try:
        # 专家模式 + 低阈值，模糊匹配更宽松
        from src.variables import CONST_UI_MODE_EXPERT

        app.ui_mode_var.set(CONST_UI_MODE_EXPERT)
        app._apply_ui_mode_settings()
        app.option_fuzzy_threshold_var.set("0.50")

        # 准备两行：其中“企业名：”应在低阈值下命中“企业名称：”
        for r in list(getattr(app, "field_rows", [])):
            r.frame.destroy()
        app.field_rows.clear()
        app._add_field_row("身份证号：", "123456789012345678")
        app._add_field_row("企业名：", "某某科技")

        # 执行
        app._on_execute_fill()

        # 断言“未找到关键词：0”
        assert app.var_missing.get().startswith("未找到关键词：")
        val = app.var_missing.get().split("：")[-1].strip()
        assert val.startswith("0")
    finally:
        app.destroy()

