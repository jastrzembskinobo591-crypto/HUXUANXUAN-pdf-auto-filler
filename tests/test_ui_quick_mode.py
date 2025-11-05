from __future__ import annotations

import pytest


def _safe_create_app():
    """尝试创建 GUI 应用实例；若当前环境不可用 Tk，则跳过测试。"""
    try:
        from src.ui import PdfFillerApp  # 延迟导入，避免无图形环境时报错
        app = PdfFillerApp()
        return app
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Tk/GUI 不可用，跳过 GUI 测试：{exc}")


def _collect_fields(app) -> dict[str, str]:
    # 将界面上的字段行采集为 {keyword: value}
    return {r.keyword_var.get(): r.value_var.get() for r in getattr(app, "field_rows", [])}


def test_quick_fill_and_clear_sets_values():
    from src.variables import CONST_UI_QUICK_FIELD_PRESETS, CONST_UI_MODE_QUICK

    app = _safe_create_app()
    try:
        # 确保处于快速模式
        app.ui_mode_var.set(CONST_UI_MODE_QUICK)
        app._apply_ui_mode_settings()

        # 执行“一键填充常用字段”
        app._on_quick_fill_fields()
        fields = _collect_fields(app)
        for k, v in dict(CONST_UI_QUICK_FIELD_PRESETS).items():
            assert k in fields
            assert fields[k] == v

        # 清空填充值
        app._on_quick_clear_fields()
        fields_after = _collect_fields(app)
        # 所有行的值均应被清空
        assert all((val == "" for val in fields_after.values()))
    finally:
        app.destroy()


def test_quick_helpers_visibility_toggle():
    from src.variables import CONST_UI_MODE_QUICK, CONST_UI_MODE_EXPERT

    app = _safe_create_app()
    try:
        # 快速模式：应展示“常用字段”与“模板引导”区域
        app.ui_mode_var.set(CONST_UI_MODE_QUICK)
        app._apply_ui_mode_settings()
        helper_frame = getattr(app, "_quick_helper_frame", None)
        template_guide = getattr(app, "_template_guide_frame", None)
        assert helper_frame is not None and helper_frame.winfo_manager()
        assert template_guide is not None and template_guide.winfo_manager()

        # 切换为专家模式：上述区域应被隐藏
        app.ui_mode_var.set(CONST_UI_MODE_EXPERT)
        app._apply_ui_mode_settings()
        assert not helper_frame.winfo_manager()
        assert not template_guide.winfo_manager()
    finally:
        app.destroy()


