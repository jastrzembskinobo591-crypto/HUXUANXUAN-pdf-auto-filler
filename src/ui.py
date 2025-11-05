"""
文件路径：src/ui.py

模块职责：
- 提供 tkinter 图形界面，遵循《PDF自动填充工具 - 产品设计与页面样式设计.md》的布局思想：
  顶部导航 + 左侧配置 + 中间预览 + 右侧状态 + 底部操作。
- 与业务层解耦：界面仅调用 data_handler 与 pdf_processor 的公共 API，通用逻辑复用 components。

变量引用说明（来自 src/variables.py）：
- PATH_DEFAULT_INPUT_PDF, PATH_TEMPLATES_JSON, PATH_EXAMPLES_DIR, PATH_OUTPUT_DIR
- STYLE_GUI_*（多项颜色/尺寸/字体），STYLE_FONT_NAME_CJK_PREFERRED
- CONST_UI_MODE_DEFAULT, CONST_UI_MODE_QUICK, CONST_UI_MODE_EXPERT

组件调用说明（来自 src/components.py / src/data_handler.py / src/pdf_processor.py）：
- get_logger, FileHandler.ensure_project_dirs / timestamped_output_path / indexed_output_path
- load_keywords_config, sanitize_input_data, load_templates_index, infer_template_id_from_filename
- PDFProcessor.fill_by_keywords

说明：
- 预览区当前为占位实现（不引入额外第三方库），后续可接入 PDF 渲染（如 PyMuPDF/Pillow）。
- 已实现的功能：选择 PDF、动态增删字段、加载关键词配置为字段、执行填充、保存结果、重置、退出。

给零基础用户的小提示（仅注释）：
- 打开 GUI 的方式：在命令行运行 `python main.py --gui` 即可启动界面。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from .components import FileHandler, get_logger
from .data_handler import (
    load_keywords_config,
    sanitize_input_data,
    load_templates_index,
    infer_template_id_from_filename,
    load_batch_json,
    load_batch_csv,
)
from .pdf_processor import PDFProcessor
from .variables import (
    PATH_DEFAULT_INPUT_PDF,
    PATH_EXAMPLES_DIR,
    PATH_TEMPLATES_JSON,
    PATH_OUTPUT_DIR,
    CONST_FUZZY_MATCH_THRESHOLD,
    CONST_ENABLE_CLAMP_DEFAULT,
    CONST_CLAMP_MARGIN_DEFAULT,
    CONST_RASTER_SCALE,
    CONST_BATCH_AUTO_TEMPLATE_DEFAULT,
    CONST_INDEX_PAD_WIDTH_DEFAULT,
    CONST_UI_MODE_DEFAULT,
    CONST_UI_MODE_EXPERT,
    CONST_UI_MODE_QUICK,
    CONST_UI_QUICK_FIELD_PRESETS,
    STYLE_GUI_ACCENT_BLUE,
    STYLE_GUI_BG,
    STYLE_GUI_CARD_BG,
    STYLE_GUI_DIVIDER,
    STYLE_GUI_FONT_FAMILY,
    STYLE_GUI_FONT_SIZE_BODY,
    STYLE_GUI_FONT_SIZE_TITLE,
    STYLE_GUI_LEFT_PANEL_WIDTH,
    STYLE_GUI_CENTER_PANEL_WIDTH,
    STYLE_GUI_RIGHT_PANEL_WIDTH,
    STYLE_GUI_PRIMARY_COLOR,
    STYLE_GUI_SUCCESS_GREEN,
    STYLE_GUI_WARN_ORANGE,
    STYLE_GUI_MUTED_GRAY,
    STYLE_GUI_WINDOW_MIN_HEIGHT,
    STYLE_GUI_WINDOW_MIN_WIDTH,
)


logger = get_logger(__name__)


@dataclass
class FieldRow:
    keyword_var: tk.StringVar
    value_var: tk.StringVar
    frame: tk.Frame


class PdfFillerApp(tk.Tk):
    """tkinter 图形界面主应用。"""

    def __init__(self) -> None:
        super().__init__()
        self.title("PDF自动填充工具（银行专用版）")
        self.minsize(STYLE_GUI_WINDOW_MIN_WIDTH, STYLE_GUI_WINDOW_MIN_HEIGHT)
        self.configure(bg=STYLE_GUI_BG)

        FileHandler.ensure_project_dirs()

        # 状态数据
        self.input_pdf: Path = PATH_DEFAULT_INPUT_PDF
        self.last_output: Optional[Path] = None
        self.last_output_size_bytes: Optional[int] = None
        self.field_rows: List[FieldRow] = []
        # 模式数据
        self.ui_mode_var = tk.StringVar(value=CONST_UI_MODE_DEFAULT)
        # 选项数据
        self.option_engine_var = tk.StringVar(value="pymupdf")
        self.option_pages_var = tk.StringVar(value="")  # 如：all 或 1,3-5
        self.option_fuzzy_threshold_var = tk.StringVar(value=str(CONST_FUZZY_MATCH_THRESHOLD))
        self.option_output_prefix_var = tk.StringVar(value="")
        self.option_enable_clamp_var = tk.BooleanVar(value=CONST_ENABLE_CLAMP_DEFAULT)
        self.option_clamp_margin_var = tk.StringVar(value=str(CONST_CLAMP_MARGIN_DEFAULT))
        self.option_raster_scale_var = tk.DoubleVar(value=float(CONST_RASTER_SCALE))
        self.option_batch_auto_template_var = tk.BooleanVar(value=bool(CONST_BATCH_AUTO_TEMPLATE_DEFAULT))
        # 批量相关
        self.batch_json_path_var = tk.StringVar(value="")
        self.batch_csv_path_var = tk.StringVar(value="")
        self.batch_output_dir_var = tk.StringVar(value="")  # 留空表示使用默认 output/
        self.option_index_width_var = tk.StringVar(value=str(CONST_INDEX_PAD_WIDTH_DEFAULT))

        # 布局
        self._build_top_nav()
        self._build_main_layout()
        self._build_bottom_bar()

        # 初始字段：尝试从关键词配置加载常见字段
        self._load_fields_from_keywords_config()

    # -----------------------------
    # 构建 UI
    # -----------------------------
    def _build_top_nav(self) -> None:
        bar = tk.Frame(self, bg=STYLE_GUI_PRIMARY_COLOR, height=44)
        bar.pack(side=tk.TOP, fill=tk.X)

        title = tk.Label(
            bar,
            text="PDF自动填充工具（银行专用版）",
            fg="#FFFFFF",
            bg=STYLE_GUI_PRIMARY_COLOR,
            font=(STYLE_GUI_FONT_FAMILY, STYLE_GUI_FONT_SIZE_TITLE, "bold"),
        )
        title.pack(side=tk.LEFT, padx=12)

        help_btn = tk.Button(
            bar,
            text="帮助",
            command=self._on_help,
            bg=STYLE_GUI_PRIMARY_COLOR,
            fg="#FFFFFF",
            bd=0,
            activebackground=STYLE_GUI_ACCENT_BLUE,
            cursor="hand2",
        )
        help_btn.pack(side=tk.RIGHT, padx=6, pady=6)

        about_btn = tk.Button(
            bar,
            text="关于",
            command=self._on_about,
            bg=STYLE_GUI_PRIMARY_COLOR,
            fg="#FFFFFF",
            bd=0,
            activebackground=STYLE_GUI_ACCENT_BLUE,
            cursor="hand2",
        )
        about_btn.pack(side=tk.RIGHT, padx=6, pady=6)

    def _build_main_layout(self) -> None:
        container = tk.Frame(self, bg=STYLE_GUI_BG)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        container.grid_columnconfigure(0, minsize=STYLE_GUI_LEFT_PANEL_WIDTH)
        container.grid_columnconfigure(1, minsize=STYLE_GUI_CENTER_PANEL_WIDTH, weight=1)
        container.grid_columnconfigure(2, minsize=STYLE_GUI_RIGHT_PANEL_WIDTH)
        container.grid_rowconfigure(0, weight=1)

        # 左侧配置区
        self.left_panel = tk.Frame(container, bg=STYLE_GUI_CARD_BG, bd=1, relief=tk.GROOVE)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._build_left_config(self.left_panel)

        # 中间预览区
        self.center_panel = tk.Frame(container, bg=STYLE_GUI_BG)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self._build_center_preview(self.center_panel)

        # 右侧辅助区
        self.right_panel = tk.Frame(container, bg=STYLE_GUI_CARD_BG, bd=1, relief=tk.GROOVE)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=8, pady=8)
        self._build_right_status(self.right_panel)

    def _build_bottom_bar(self) -> None:
        bar = tk.Frame(self, bg="#FAFAFA", height=60)
        bar.pack(side=tk.BOTTOM, fill=tk.X)

        exec_btn = tk.Button(
            bar,
            text="执行填充",
            command=self._on_execute_fill,
            bg=STYLE_GUI_PRIMARY_COLOR,
            fg="#FFFFFF",
            padx=16,
            pady=8,
        )
        exec_btn.pack(side=tk.LEFT, padx=10, pady=10)

        save_btn = tk.Button(
            bar,
            text="保存结果",
            command=self._on_save_result,
            bg=STYLE_GUI_PRIMARY_COLOR,
            fg="#FFFFFF",
            padx=16,
            pady=8,
        )
        save_btn.pack(side=tk.LEFT, padx=10, pady=10)

        reset_btn = tk.Button(bar, text="重置", command=self._on_reset)
        reset_btn.pack(side=tk.LEFT, padx=10, pady=10)

        adjust_btn = tk.Button(bar, text="坐标微调（预留）", command=self._on_adjust)
        adjust_btn.pack(side=tk.LEFT, padx=10, pady=10)

        exit_btn = tk.Button(bar, text="退出", command=self.destroy)
        exit_btn.pack(side=tk.RIGHT, padx=10, pady=10)

    # 左侧配置内容
    def _build_left_config(self, parent: tk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        # 模式切换卡片
        mode_card = tk.LabelFrame(parent, text="模式切换", bg=STYLE_GUI_CARD_BG, fg="#000000")
        mode_card.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        tk.Radiobutton(
            mode_card,
            text="快速模式",
            value=CONST_UI_MODE_QUICK,
            variable=self.ui_mode_var,
            command=self._on_mode_change,
            bg=STYLE_GUI_CARD_BG,
        ).grid(row=0, column=0, padx=8, pady=6, sticky="w")
        tk.Radiobutton(
            mode_card,
            text="专家模式",
            value=CONST_UI_MODE_EXPERT,
            variable=self.ui_mode_var,
            command=self._on_mode_change,
            bg=STYLE_GUI_CARD_BG,
        ).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        self._mode_tip_label = tk.Label(
            mode_card,
            text="",
            bg=STYLE_GUI_CARD_BG,
            fg=STYLE_GUI_MUTED_GRAY,
            wraplength=STYLE_GUI_LEFT_PANEL_WIDTH - 40,
            justify=tk.LEFT,
        )
        self._mode_tip_label.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w")

        # 文件选择卡片
        file_card = tk.LabelFrame(parent, text="文件选择", bg=STYLE_GUI_CARD_BG, fg="#000000")
        file_card.grid(row=1, column=0, sticky="ew", padx=12, pady=10)

        self.input_path_var = tk.StringVar(value=str(self.input_pdf))
        path_entry = tk.Entry(file_card, textvariable=self.input_path_var)
        path_entry.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        file_card.grid_columnconfigure(0, weight=1)

        choose_btn = tk.Button(file_card, text="浏览文件", command=self._on_choose_pdf)
        choose_btn.grid(row=0, column=1, padx=8, pady=8)

        gen_btn = tk.Button(file_card, text="生成示例", command=self._on_make_example)
        gen_btn.grid(row=0, column=2, padx=8, pady=8)

        # 选项卡片
        opts_card = tk.LabelFrame(parent, text="选项", bg=STYLE_GUI_CARD_BG, fg="#000000")
        opts_card.grid(row=2, column=0, sticky="ew", padx=12, pady=6)

        tk.Label(opts_card, text="引擎", bg=STYLE_GUI_CARD_BG).grid(row=0, column=0, padx=8, pady=6, sticky="w")
        engine_cb = ttk.Combobox(
            opts_card,
            textvariable=self.option_engine_var,
            values=["pymupdf", "reportlab", "raster"],
            state="readonly",
            width=12,
        )
        engine_cb.grid(row=0, column=1, padx=8, pady=6, sticky="w")

        tk.Label(opts_card, text="页选择", bg=STYLE_GUI_CARD_BG).grid(row=1, column=0, padx=8, pady=6, sticky="w")
        tk.Entry(opts_card, textvariable=self.option_pages_var, width=16).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(opts_card, text="(all 或 1,3-5)", bg=STYLE_GUI_CARD_BG, fg=STYLE_GUI_MUTED_GRAY).grid(row=1, column=2, padx=4, pady=6, sticky="w")

        tk.Label(opts_card, text="模糊阈值 (0~1)", bg=STYLE_GUI_CARD_BG).grid(row=2, column=0, padx=8, pady=6, sticky="w")
        tk.Entry(opts_card, textvariable=self.option_fuzzy_threshold_var, width=10).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        tk.Label(opts_card, text=f"默认 {CONST_FUZZY_MATCH_THRESHOLD}", bg=STYLE_GUI_CARD_BG, fg=STYLE_GUI_MUTED_GRAY).grid(row=2, column=2, padx=4, pady=6, sticky="w")

        tk.Label(opts_card, text="输出前缀", bg=STYLE_GUI_CARD_BG).grid(row=3, column=0, padx=8, pady=6, sticky="w")
        tk.Entry(opts_card, textvariable=self.option_output_prefix_var, width=20).grid(row=3, column=1, padx=8, pady=6, sticky="w")

        # 贴边保护开关
        tk.Label(opts_card, text="贴边保护", bg=STYLE_GUI_CARD_BG).grid(row=4, column=0, padx=8, pady=6, sticky="w")
        tk.Checkbutton(
            opts_card,
            variable=self.option_enable_clamp_var,
            onvalue=True,
            offvalue=False,
            bg=STYLE_GUI_CARD_BG,
        ).grid(row=4, column=1, padx=8, pady=6, sticky="w")

        # 边距（pt）
        tk.Label(opts_card, text="边距 (pt)", bg=STYLE_GUI_CARD_BG).grid(row=5, column=0, padx=8, pady=6, sticky="w")
        tk.Entry(opts_card, textvariable=self.option_clamp_margin_var, width=10).grid(row=5, column=1, padx=8, pady=6, sticky="w")

        # Raster 清晰度（仅在选择 raster 引擎时生效）
        tk.Label(opts_card, text="清晰度（raster）", bg=STYLE_GUI_CARD_BG).grid(row=6, column=0, padx=8, pady=6, sticky="w")
        scale_widget = tk.Scale(
            opts_card,
            variable=self.option_raster_scale_var,
            from_=0.5,
            to=4.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            length=160,
        )
        scale_widget.grid(row=6, column=1, padx=8, pady=6, sticky="w")
        self._raster_scale_value_label = tk.Label(
            opts_card, text=f"x{self.option_raster_scale_var.get():.1f}", bg=STYLE_GUI_CARD_BG, fg=STYLE_GUI_MUTED_GRAY
        )
        self._raster_scale_value_label.grid(row=6, column=2, padx=4, pady=6, sticky="w")

        def _on_scale_change(_: str) -> None:
            try:
                self._raster_scale_value_label.config(text=f"x{float(self.option_raster_scale_var.get()):.1f}")
            except Exception:
                pass

        scale_widget.configure(command=_on_scale_change)

        # 批量：逐份自动匹配模板ID（开关，仅批量模式生效；单次模式将按文件名自动匹配）
        tk.Label(opts_card, text="逐份自动匹配（批量）", bg=STYLE_GUI_CARD_BG).grid(row=7, column=0, padx=8, pady=6, sticky="w")
        tk.Checkbutton(
            opts_card,
            variable=self.option_batch_auto_template_var,
            onvalue=True,
            offvalue=False,
            bg=STYLE_GUI_CARD_BG,
        ).grid(row=7, column=1, padx=8, pady=6, sticky="w")
        tk.Label(
            opts_card,
            text="批量时逐条按文件名匹配模板；单次将自动匹配",
            bg=STYLE_GUI_CARD_BG,
            fg=STYLE_GUI_MUTED_GRAY,
        ).grid(row=7, column=2, padx=4, pady=6, sticky="w")

        # 字段配置卡片
        fields_card = tk.LabelFrame(parent, text="填充字段配置", bg=STYLE_GUI_CARD_BG, fg="#000000")
        fields_card.grid(row=3, column=0, sticky="nsew", padx=12, pady=10)
        fields_card.grid_columnconfigure(0, weight=1)

        header = tk.Frame(fields_card, bg=STYLE_GUI_CARD_BG)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text="关键词", bg=STYLE_GUI_CARD_BG).grid(row=0, column=0, padx=8, pady=6)
        tk.Label(header, text="填充值", bg=STYLE_GUI_CARD_BG).grid(row=0, column=1, padx=8, pady=6)

        self.fields_container = tk.Frame(fields_card, bg=STYLE_GUI_CARD_BG)
        self.fields_container.grid(row=1, column=0, sticky="nsew")
        fields_card.grid_rowconfigure(1, weight=1)

        ctrl = tk.Frame(fields_card, bg=STYLE_GUI_CARD_BG)
        ctrl.grid(row=2, column=0, sticky="ew", pady=6)
        tk.Button(ctrl, text="+ 添加字段", command=lambda: self._add_field_row()).pack(side=tk.LEFT, padx=6)
        tk.Button(ctrl, text="保存模板", command=self._on_save_template).pack(side=tk.LEFT, padx=6)
        tk.Button(ctrl, text="加载模板", command=self._on_load_template).pack(side=tk.LEFT, padx=6)

        # 模板引导（快速模式下显示）
        template_guide = tk.Frame(ctrl, bg=STYLE_GUI_CARD_BG)
        self._template_guide_frame = template_guide
        tk.Button(
            template_guide,
            text="打开模板配置",
            command=self._on_open_templates_json,
        ).pack(side=tk.LEFT, padx=(6, 4))
        tk.Label(
            template_guide,
            text="未显式选择时将按文件名自动匹配 templates.json；亦可保存/加载模板",
            bg=STYLE_GUI_CARD_BG,
            fg=STYLE_GUI_MUTED_GRAY,
            wraplength=STYLE_GUI_LEFT_PANEL_WIDTH - 80,
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, padx=2)

        quick_helpers = tk.Frame(ctrl, bg=STYLE_GUI_CARD_BG)
        self._quick_helper_frame = quick_helpers
        self._quick_fill_btn = tk.Button(
            quick_helpers,
            text="一键填充常用字段",
            command=self._on_quick_fill_fields,
        )
        self._quick_fill_btn.pack(side=tk.LEFT, padx=6)
        self._quick_clear_btn = tk.Button(
            quick_helpers,
            text="清空填充值",
            command=self._on_quick_clear_fields,
        )
        self._quick_clear_btn.pack(side=tk.LEFT, padx=6)

        # 批量卡片
        batch_card = tk.LabelFrame(parent, text="批量模式（可选）", bg=STYLE_GUI_CARD_BG, fg="#000000")
        batch_card.grid(row=4, column=0, sticky="ew", padx=12, pady=10)
        batch_card.grid_columnconfigure(1, weight=1)

        tk.Label(batch_card, text="批量 JSON", bg=STYLE_GUI_CARD_BG).grid(row=0, column=0, padx=8, pady=6, sticky="w")
        tk.Entry(batch_card, textvariable=self.batch_json_path_var).grid(row=0, column=1, padx=8, pady=6, sticky="ew")
        tk.Button(batch_card, text="浏览", command=self._on_choose_batch_json).grid(row=0, column=2, padx=8, pady=6)

        tk.Label(batch_card, text="批量 CSV", bg=STYLE_GUI_CARD_BG).grid(row=1, column=0, padx=8, pady=6, sticky="w")
        tk.Entry(batch_card, textvariable=self.batch_csv_path_var).grid(row=1, column=1, padx=8, pady=6, sticky="ew")
        tk.Button(batch_card, text="浏览", command=self._on_choose_batch_csv).grid(row=1, column=2, padx=8, pady=6)

        tk.Label(batch_card, text="输出目录", bg=STYLE_GUI_CARD_BG).grid(row=2, column=0, padx=8, pady=6, sticky="w")
        tk.Entry(batch_card, textvariable=self.batch_output_dir_var).grid(row=2, column=1, padx=8, pady=6, sticky="ew")
        tk.Button(batch_card, text="选择文件夹", command=self._on_choose_batch_output_dir).grid(row=2, column=2, padx=8, pady=6)

        tk.Label(batch_card, text="序号宽度", bg=STYLE_GUI_CARD_BG).grid(row=3, column=0, padx=8, pady=6, sticky="w")
        tk.Entry(batch_card, textvariable=self.option_index_width_var, width=8).grid(row=3, column=1, padx=8, pady=6, sticky="w")
        tk.Label(batch_card, text="留空表示默认 3；仅批量模式生效", bg=STYLE_GUI_CARD_BG, fg=STYLE_GUI_MUTED_GRAY).grid(row=3, column=2, padx=4, pady=6, sticky="w")

        # 保存引用供模式切换使用
        self._opts_card = opts_card
        self._batch_card = batch_card

        self._apply_ui_mode_settings()

    def _apply_ui_mode_settings(self) -> None:
        """根据当前模式显示或隐藏高级配置区域。"""

        mode = CONST_UI_MODE_DEFAULT
        try:
            mode = self.ui_mode_var.get().strip().lower()
        except Exception:
            mode = CONST_UI_MODE_DEFAULT

        opts_card = getattr(self, "_opts_card", None)
        batch_card = getattr(self, "_batch_card", None)

        if mode == CONST_UI_MODE_QUICK:
            if opts_card is not None and opts_card.winfo_manager():
                opts_card.grid_remove()
            if batch_card is not None and batch_card.winfo_manager():
                batch_card.grid_remove()
        else:
            if opts_card is not None and not opts_card.winfo_manager():
                opts_card.grid()
            if batch_card is not None and not batch_card.winfo_manager():
                batch_card.grid()

        self._update_mode_tip_text(mode)
        self._update_quick_helpers_visibility(mode)

    def _update_mode_tip_text(self, mode: str) -> None:
        """刷新模式提示文案。"""

        tip_label = getattr(self, "_mode_tip_label", None)
        if tip_label is None:
            return

        if mode == CONST_UI_MODE_QUICK:
            tip_label.config(text="快速模式：仅需选择PDF并填写字段，其余选项使用推荐默认值。")
        elif mode == CONST_UI_MODE_EXPERT:
            tip_label.config(text="专家模式：开放引擎、页选择、批量处理等高级设置，适合进阶配置。")
        else:
            tip_label.config(text="请选择适合的模式。")

    def _on_mode_change(self) -> None:
        """模式切换事件，刷新界面布局。"""

        mode = ""
        try:
            mode = self.ui_mode_var.get()
        except Exception:
            mode = CONST_UI_MODE_DEFAULT
        logger.info("GUI 切换模式：%s", mode)
        self._apply_ui_mode_settings()

    def _update_quick_helpers_visibility(self, mode: str) -> None:
        """在快速模式下展示常用字段辅助按钮，其余模式隐藏。"""

        helper_frame = getattr(self, "_quick_helper_frame", None)
        template_guide = getattr(self, "_template_guide_frame", None)
        if helper_frame is None:
            return

        if mode == CONST_UI_MODE_QUICK:
            if not helper_frame.winfo_manager():
                helper_frame.pack(side=tk.RIGHT, padx=6)
            if template_guide is not None and not template_guide.winfo_manager():
                template_guide.pack(side=tk.LEFT, padx=6)
        else:
            if helper_frame.winfo_manager():
                helper_frame.pack_forget()
            if template_guide is not None and template_guide.winfo_manager():
                template_guide.pack_forget()

    # 中间预览（占位实现）
    def _build_center_preview(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=STYLE_GUI_BG)
        header.pack(side=tk.TOP, fill=tk.X)
        tk.Label(header, text="预览区（缩放：100%）  ▶  上一页  下一页  适配窗口", bg=STYLE_GUI_BG).pack(side=tk.LEFT, padx=4, pady=4)

        body = tk.Frame(parent, bg=STYLE_GUI_BG)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = tk.Frame(body, bg="#FFFFFF", bd=1, relief=tk.SOLID)
        mid = tk.Frame(body, width=8, bg=STYLE_GUI_DIVIDER)
        right = tk.Frame(body, bg="#FFFFFF", bd=1, relief=tk.SOLID)

        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        mid.pack(side=tk.LEFT, fill=tk.Y)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_orig = tk.Canvas(left, bg="#FFFFFF")
        self.canvas_orig.pack(fill=tk.BOTH, expand=True)
        self.canvas_orig.create_text(200, 100, text="原文件预览（后续接入 PDF 渲染）", fill=STYLE_GUI_MUTED_GRAY)

        self.canvas_filled = tk.Canvas(right, bg="#FFFFFF")
        self.canvas_filled.pack(fill=tk.BOTH, expand=True)
        self.canvas_filled.create_text(200, 100, text="填充后预览（生成后可提示打开文件夹）", fill=STYLE_GUI_MUTED_GRAY)

    # 右侧状态
    def _build_right_status(self, parent: tk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        status_card = tk.LabelFrame(parent, text="填充状态", bg=STYLE_GUI_CARD_BG, fg="#000000")
        status_card.grid(row=0, column=0, sticky="ew", padx=12, pady=10)

        self.var_total = tk.StringVar(value="字段总数：0")
        self.var_filled = tk.StringVar(value="已填充：0")
        self.var_missing = tk.StringVar(value="未找到关键词：0")
        self.var_eta = tk.StringVar(value="预计完成时间：-")
        self.var_batch_progress = tk.StringVar(value="批量进度：-")
        self.var_size = tk.StringVar(value="输出文件大小：-")
        self.var_engine = tk.StringVar(value="实际引擎：-")
        self.var_font = tk.StringVar(value="字体来源：-")
        self.var_template = tk.StringVar(value="模板ID：-")
        self.var_last_output = tk.StringVar(value="最新输出：-")

        for i, var in enumerate([
            self.var_total,
            self.var_filled,
            self.var_missing,
            self.var_eta,
            self.var_batch_progress,
            self.var_size,
            self.var_engine,
            self.var_font,
            self.var_template,
            self.var_last_output,
        ]):
            tk.Label(status_card, textvariable=var, bg=STYLE_GUI_CARD_BG).grid(row=i, column=0, sticky="w", padx=8, pady=4)

        quick_card = tk.LabelFrame(parent, text="快捷操作", bg=STYLE_GUI_CARD_BG, fg="#000000")
        quick_card.grid(row=1, column=0, sticky="ew", padx=12, pady=10)
        tk.Button(quick_card, text="打开输出文件夹", command=self._open_output_folder).grid(row=0, column=0, padx=8, pady=6)
        tk.Button(quick_card, text="打开最新输出", command=self._open_last_output).grid(row=0, column=1, padx=8, pady=6)
        tk.Button(quick_card, text="复制输出路径", command=self._copy_last_output_path).grid(row=0, column=2, padx=8, pady=6)
        tk.Button(quick_card, text="定位输出所在目录", command=self._reveal_last_output_location).grid(row=1, column=0, padx=8, pady=6)
        tk.Button(quick_card, text="复制文件大小", command=self._copy_last_output_size).grid(row=1, column=1, padx=8, pady=6)

        faq_card = tk.LabelFrame(parent, text="常见问题", bg=STYLE_GUI_CARD_BG, fg="#000000")
        faq_card.grid(row=2, column=0, sticky="ew", padx=12, pady=10)
        tk.Label(
            faq_card,
            text="关键词未找到？检查关键词是否与PDF文本一致；本工具支持模糊匹配。",
            bg=STYLE_GUI_CARD_BG,
            wraplength=STYLE_GUI_RIGHT_PANEL_WIDTH - 40,
            justify=tk.LEFT,
        ).grid(row=0, column=0, padx=8, pady=6, sticky="w")

    # -----------------------------
    # 事件处理
    # -----------------------------
    def _on_help(self) -> None:
        messagebox.showinfo("帮助", "1) 选择PDF  2) 配置字段  3) 执行填充  4) 保存结果")

    def _on_about(self) -> None:
        messagebox.showinfo("关于", "PDF自动填充工具（银行专用版）\n关键词定位 + 坐标写入")

    def _on_choose_pdf(self) -> None:
        path = filedialog.askopenfilename(title="选择PDF文件", filetypes=[("PDF Files", "*.pdf")])
        if path:
            self.input_pdf = Path(path)
            self.input_path_var.set(str(self.input_pdf))

    def _on_choose_batch_json(self) -> None:
        path = filedialog.askopenfilename(title="选择批量 JSON 文件", filetypes=[("JSON Files", "*.json")])
        if path:
            self.batch_json_path_var.set(str(path))

    def _on_choose_batch_csv(self) -> None:
        path = filedialog.askopenfilename(title="选择批量 CSV 文件", filetypes=[("CSV Files", "*.csv")])
        if path:
            self.batch_csv_path_var.set(str(path))

    def _on_choose_batch_output_dir(self) -> None:
        path = filedialog.askdirectory(title="选择批量输出目录")
        if path:
            self.batch_output_dir_var.set(str(path))

    def _on_make_example(self) -> None:
        try:
            # 优先使用 PyMuPDF 生成并强制内嵌中文字体；失败再回退 ReportLab
            import fitz  # PyMuPDF
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            pdf_path = PATH_EXAMPLES_DIR / "blank_contract.pdf"
            PATH_EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
            used_engine = "pymupdf"
            used_font = None
            try:
                doc = fitz.open()
                page = doc.new_page(width=595.28, height=841.89)  # A4 portrait
                from .variables import PATH_FONT_FILE
                fontname = None
                if PATH_FONT_FILE and PATH_FONT_FILE.exists() and PATH_FONT_FILE.suffix.lower() in {".ttf", ".otf"}:
                    fontname = "SimHei"
                    doc.insert_font(file=str(PATH_FONT_FILE), fontname=fontname)
                    used_font = fontname
                else:
                    noto = PATH_EXAMPLES_DIR.parent / "config" / "fonts" / "NotoSansCJKsc-Regular.otf"
                    if noto.exists():
                        fontname = "NotoSansCJKsc"
                        doc.insert_font(file=str(noto), fontname=fontname)
                        used_font = fontname
                if not used_font:
                    # 兜底：PyMuPDF 的内置字体不保证中文，转回 ReportLab 路线
                    raise RuntimeError("No embeddable CJK font file found")
                page.insert_text((72, 800), "身份证号：", fontname=used_font, fontsize=12, color=(0, 0, 0))
                page.insert_text((72, 770), "企业名称：", fontname=used_font, fontsize=12, color=(0, 0, 0))
                page.insert_text((72, 740), "联系电话：", fontname=used_font, fontsize=12, color=(0, 0, 0))
                doc.save(str(pdf_path), deflate=True, clean=True, garbage=4)
                doc.close()
            except Exception:
                # 回退：使用 ReportLab + CID 字体（可能被部分阅读器显示为黑块，仅作兜底）
                used_engine = "reportlab"
                c = canvas.Canvas(str(pdf_path))
                c.setPageSize((595.28, 841.89))
                try:
                    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
                    used_font = "STSong-Light"
                except Exception:
                    used_font = "Helvetica"
                c.setFont(used_font, 12)
                c.drawString(72, 800, "身份证号：")
                c.drawString(72, 770, "企业名称：")
                c.drawString(72, 740, "联系电话：")
                c.save()

            self.input_pdf = pdf_path
            self.input_path_var.set(str(pdf_path))
            try:
                size_kb = max(1, int(pdf_path.stat().st_size / 1024))
            except Exception:
                size_kb = -1
            messagebox.showinfo("提示", f"已生成示例：{pdf_path}\n生成引擎：{used_engine}\n使用字体：{used_font}\n文件大小：{size_kb} KB")
        except Exception as exc:  # noqa: BLE001
            logger.exception("示例生成失败：%s", exc)
            messagebox.showerror("错误", f"示例生成失败：{exc}")

    def _on_save_template(self) -> None:
        try:
            data = [{"keyword": r.keyword_var.get(), "value": r.value_var.get()} for r in self.field_rows]
            PATH_TEMPLATES_JSON.parent.mkdir(parents=True, exist_ok=True)
            with open(PATH_TEMPLATES_JSON, "w", encoding="utf-8") as f:  # noqa: P103
                json.dump({"fields": data}, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("提示", f"模板已保存：{PATH_TEMPLATES_JSON}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("模板保存失败：%s", exc)
            messagebox.showerror("错误", f"模板保存失败：{exc}")

    def _on_load_template(self) -> None:
        try:
            if not PATH_TEMPLATES_JSON.exists():
                messagebox.showwarning("提示", "未找到模板文件，将忽略。")
                return
            with open(PATH_TEMPLATES_JSON, "r", encoding="utf-8") as f:  # noqa: P103
                content = json.load(f)
            fields = content.get("fields", [])
            # 清空后重建
            for r in self.field_rows:
                r.frame.destroy()
            self.field_rows.clear()
            for item in fields:
                self._add_field_row(str(item.get("keyword", "")), str(item.get("value", "")))
        except Exception as exc:  # noqa: BLE001
            logger.exception("模板加载失败：%s", exc)
            messagebox.showerror("错误", f"模板加载失败：{exc}")

    def _on_open_templates_json(self) -> None:
        """打开模板配置文件所在位置（不存在则创建默认文件再打开）。"""
        try:
            PATH_TEMPLATES_JSON.parent.mkdir(parents=True, exist_ok=True)
            if not PATH_TEMPLATES_JSON.exists():
                # 创建带最小注释/示例的默认文件（兼容新旧结构提示）
                default_content = {
                    "default": {"path": "config/keywords.json", "match_patterns": ["default"]}
                }
                try:
                    with open(PATH_TEMPLATES_JSON, "w", encoding="utf-8") as f:  # noqa: P103
                        json.dump(default_content, f, ensure_ascii=False, indent=2)
                except Exception:
                    # 若写入失败，不阻断后续打开目录
                    pass
            # 优先打开文件本身；失败则打开目录
            if sys.platform.startswith("win"):
                try:
                    os.startfile(str(PATH_TEMPLATES_JSON))  # type: ignore[attr-defined]
                except Exception:
                    os.startfile(str(PATH_TEMPLATES_JSON.parent))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                try:
                    subprocess.run(["open", str(PATH_TEMPLATES_JSON)], check=False)
                except Exception:
                    subprocess.run(["open", str(PATH_TEMPLATES_JSON.parent)], check=False)
            else:
                try:
                    subprocess.run(["xdg-open", str(PATH_TEMPLATES_JSON)], check=False)
                except Exception:
                    subprocess.run(["xdg-open", str(PATH_TEMPLATES_JSON.parent)], check=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("打开模板配置失败：%s", exc)
            messagebox.showerror("错误", f"打开模板配置失败：{exc}")

    def _on_execute_fill(self) -> None:
        try:
            # 数据收集与清洗
            data_pairs = {r.keyword_var.get(): r.value_var.get() for r in self.field_rows}
            data_pairs = sanitize_input_data(data_pairs)

            # 更新状态统计
            self.var_total.set(f"字段总数：{len(self.field_rows)}")
            self.var_filled.set(f"已填充：{len(data_pairs)}")

            # 读取 GUI 选项（通用）
            engine = self.option_engine_var.get().strip() or "pymupdf"
            pages = self.option_pages_var.get().strip() or None
            # 模糊阈值（可选）
            fuzzy_threshold = None
            raw_thr = (self.option_fuzzy_threshold_var.get() or "").strip()
            if raw_thr:
                try:
                    fuzzy_threshold = float(raw_thr)
                    if not (0.0 <= fuzzy_threshold <= 1.0):
                        raise ValueError("阈值需在 0~1 之间")
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror("参数错误", f"模糊阈值无效，请输入 0~1 的数字：{exc}")
                    return
            enable_clamp = bool(self.option_enable_clamp_var.get())
            margin_raw = (self.option_clamp_margin_var.get() or "").strip()
            if margin_raw:
                try:
                    clamp_margin = float(margin_raw)
                    if clamp_margin < 0:
                        raise ValueError("边距需为非负数")
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror("参数错误", f"边距无效，请输入非负数字：{exc}")
                    return
            else:
                clamp_margin = CONST_CLAMP_MARGIN_DEFAULT

            raster_scale = None
            if engine == "raster":
                try:
                    raster_scale = float(self.option_raster_scale_var.get())
                except Exception:
                    raster_scale = None

            # 批量模式检测：若提供了 JSON 或 CSV 路径，进入批量流程
            batch_json_path = Path(self.batch_json_path_var.get().strip()) if self.batch_json_path_var.get().strip() else None
            batch_csv_path = Path(self.batch_csv_path_var.get().strip()) if self.batch_csv_path_var.get().strip() else None

            if (batch_json_path and batch_json_path.exists()) or (batch_csv_path and batch_csv_path.exists()):
                # 批量数据加载
                records: List[Dict[str, str]] = []  # type: ignore[name-defined]
                if batch_json_path and batch_json_path.exists():
                    records = load_batch_json(batch_json_path)
                elif batch_csv_path and batch_csv_path.exists():
                    records = load_batch_csv(batch_csv_path)
                if not records:
                    messagebox.showwarning("提示", "未从批量数据中解析到任何记录")
                    return
                total_records = len(records)
                self._set_batch_progress(0, total_records)

                # 模板索引与默认覆盖
                templates_mapping = load_templates_index()
                default_kw_config_path = None
                try:
                    auto_tid = infer_template_id_from_filename(self.input_pdf)
                    if auto_tid and auto_tid in templates_mapping:
                        default_kw_config_path = Path(templates_mapping[auto_tid])
                except Exception:
                    default_kw_config_path = None
                default_kw_overrides = load_keywords_config(default_kw_config_path)

                # 批量自动匹配开关
                use_batch_auto_template = bool(self.option_batch_auto_template_var.get())

                # 输出目录（可选重定向）
                batch_out_dir = None
                raw_dir = (self.batch_output_dir_var.get() or "").strip()
                if raw_dir:
                    try:
                        batch_out_dir = Path(raw_dir)
                        batch_out_dir.mkdir(parents=True, exist_ok=True)
                    except Exception as exc:  # noqa: BLE001
                        messagebox.showerror("目录错误", f"批量输出目录不可用：{exc}")
                        return

                processor = PDFProcessor()
                outputs: List[Path] = []  # type: ignore[name-defined]
                prefix = self.option_output_prefix_var.get().strip()
                try:
                    index_width = int(self.option_index_width_var.get().strip()) if self.option_index_width_var.get().strip() else CONST_INDEX_PAD_WIDTH_DEFAULT
                    if index_width <= 0:
                        index_width = CONST_INDEX_PAD_WIDTH_DEFAULT
                except Exception:
                    index_width = CONST_INDEX_PAD_WIDTH_DEFAULT

                for i, record in enumerate(records, start=1):
                    if not record:
                        continue
                    # 每条记录允许保留键覆盖：__input_pdf / __template_id / __keywords_json
                    local_input_pdf = self.input_pdf
                    if record.get("__input_pdf"):
                        try:
                            cand = Path(str(record.get("__input_pdf")))
                            if cand.exists() and cand.is_file():
                                local_input_pdf = cand
                            else:
                                logger.warning("GUI 批量：第 %s 条记录的 __input_pdf 不存在或不可用：%s，回退全局输入", i, record.get("__input_pdf"))
                        except Exception:
                            logger.warning("GUI 批量：第 %s 条记录的 __input_pdf 无法解析：%s，回退全局输入", i, record.get("__input_pdf"))

                    rec_kw_config_path = default_kw_config_path
                    # 记录层覆盖
                    if record.get("__keywords_json"):
                        try:
                            rec_kw = Path(str(record.get("__keywords_json")))
                            if rec_kw.exists():
                                rec_kw_config_path = rec_kw
                                logger.info("GUI 批量：第 %s 条记录使用 __keywords_json：%s", i, rec_kw)
                        except Exception:
                            logger.warning("GUI 批量：第 %s 条记录的 __keywords_json 无法解析，忽略", i)
                    elif record.get("__template_id"):
                        rec_tid = str(record.get("__template_id")).strip()
                        if rec_tid in templates_mapping:
                            rec_kw_config_path = Path(templates_mapping[rec_tid])
                            logger.info("GUI 批量：第 %s 条记录使用 __template_id=%s -> %s", i, rec_tid, rec_kw_config_path)
                        else:
                            logger.warning("GUI 批量：第 %s 条记录提供的 __template_id=%s 未在 templates.json 中找到，忽略", i, rec_tid)
                    elif use_batch_auto_template:
                        auto_tid = infer_template_id_from_filename(local_input_pdf)
                        if auto_tid and auto_tid in templates_mapping:
                            rec_kw_config_path = Path(templates_mapping[auto_tid])
                            logger.info("GUI 批量：第 %s 条记录自动匹配模板ID=%s，使用配置：%s", i, auto_tid, rec_kw_config_path)

                    kw_overrides = load_keywords_config(rec_kw_config_path)
                    clean_record = {k: v for k, v in record.items() if not str(k).startswith("__")}

                    out_path = FileHandler.indexed_output_path(
                        local_input_pdf,
                        index=i,
                        pad=index_width,
                        prefix=(prefix if prefix else None),
                    )
                    if batch_out_dir:
                        out_path = batch_out_dir / out_path.name

                    result = processor.fill_by_keywords(
                        local_input_pdf,
                        clean_record,
                        per_key_overrides=kw_overrides,
                        output_path=out_path,
                        pages=pages,
                        fuzzy_threshold=fuzzy_threshold,
                        engine=engine,
                        enable_clamp=enable_clamp,
                        clamp_margin=clamp_margin,
                        raster_scale=raster_scale,
                    )
                    outputs.append(result)
                    self._set_batch_progress(i, total_records)

                self.last_output = outputs[-1] if outputs else None
                self.var_template.set("模板ID：batch")
                self.var_eta.set("预计完成时间：<1秒")
                self._set_batch_progress(len(outputs), total_records)
                self._update_last_output_status(self.last_output, processor, engine)
                messagebox.showinfo("完成", f"批量填充完成，共生成 {len(outputs)} 个文件。\n最后一个输出：{self.last_output if self.last_output else '-'}")
                return

            # —— 单次模式 ——
            # 加载关键词覆盖配置：基于输入文件名自动匹配模板ID
            kw_config_path = None
            try:
                mapping = load_templates_index()
                auto_tid = infer_template_id_from_filename(self.input_pdf)
                if auto_tid and auto_tid in mapping:
                    from pathlib import Path as _P

                    kw_config_path = _P(mapping[auto_tid])
                    logger.info("GUI: 已基于文件名自动匹配模板ID=%s，使用配置：%s", auto_tid, kw_config_path)
                    self.var_template.set(f"模板ID：{auto_tid}")
                else:
                    self.var_template.set("模板ID：default")
            except Exception:
                self.var_template.set("模板ID：-")
            kw_overrides = load_keywords_config(kw_config_path)

            processor = PDFProcessor()
            prefix = self.option_output_prefix_var.get().strip()
            out_path = FileHandler.timestamped_output_path(self.input_pdf, prefix=(prefix if prefix else None))

            out = processor.fill_by_keywords(
                self.input_pdf,
                data_pairs,
                per_key_overrides=kw_overrides,
                output_path=out_path,
                pages=pages,
                fuzzy_threshold=fuzzy_threshold,
                engine=engine,
                enable_clamp=enable_clamp,
                clamp_margin=clamp_margin,
                raster_scale=raster_scale,
            )
            self.last_output = out
            self.var_eta.set("预计完成时间：<1秒")
            self._set_batch_progress(0, 0)
            self._update_last_output_status(out, processor, engine)
            # 更新未命中统计（右侧状态卡）
            try:
                stats = getattr(processor, "last_fill_stats", None)
                miss_n = int(stats.get("missing_count", 0)) if isinstance(stats, dict) else 0
                self.var_missing.set(f"未找到关键词：{miss_n}")
            except Exception:
                pass
            messagebox.showinfo("完成", f"填充完成，保存至：{out}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("执行填充失败：%s", exc)
            messagebox.showerror("错误", f"执行填充失败：{exc}")

    def _on_save_result(self) -> None:
        if not self.last_output or not self.last_output.exists():
            messagebox.showwarning("提示", "暂无可保存的结果，请先执行填充。")
            return
        target = filedialog.asksaveasfilename(title="保存结果PDF", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if target:
            try:
                shutil.copyfile(self.last_output, target)
                messagebox.showinfo("提示", f"已保存到：{target}")
            except Exception as exc:  # noqa: BLE001
                logger.exception("保存失败：%s", exc)
                messagebox.showerror("错误", f"保存失败：{exc}")

    def _on_reset(self) -> None:
        for r in self.field_rows:
            r.value_var.set("")
        self.var_filled.set("已填充：0")
        self.var_missing.set("未找到关键词：0")
        self.var_eta.set("预计完成时间：-")
        self._set_batch_progress(0, 0)

    def _on_quick_fill_fields(self) -> None:
        """快速模式：一键填充常用字段示例数据。"""

        try:
            presets = dict(CONST_UI_QUICK_FIELD_PRESETS)
            if not presets:
                messagebox.showwarning("提示", "尚未配置常用字段预设，请联系管理员补充。")
                return

            existing = {row.keyword_var.get(): row for row in self.field_rows}
            for keyword, value in presets.items():
                key = str(keyword)
                if key in existing:
                    existing[key].value_var.set(value)
                else:
                    self._add_field_row(key, value)
                    existing[key] = self.field_rows[-1]

            filled_count = sum(1 for row in self.field_rows if row.value_var.get())
            self.var_filled.set(f"已填充：{filled_count}")
            messagebox.showinfo("提示", "常用字段示例已填充，可按需调整后执行填充。")
        except Exception as exc:  # noqa: BLE001
            logger.exception("快速填充常用字段失败：%s", exc)
            messagebox.showerror("错误", f"常用字段填充失败：{exc}")

    def _on_quick_clear_fields(self) -> None:
        """快速模式：清空当前字段填充值。"""

        try:
            for row in self.field_rows:
                row.value_var.set("")
            self.var_filled.set("已填充：0")
            messagebox.showinfo("提示", "已清空所有填充值。")
        except Exception as exc:  # noqa: BLE001
            logger.exception("快速清空填充值失败：%s", exc)
            messagebox.showerror("错误", f"清空填充值失败：{exc}")

    def _on_adjust(self) -> None:
        messagebox.showinfo("提示", "坐标微调将在后续版本提供。")

    def _open_output_folder(self) -> None:
        path = self.last_output.parent if self.last_output else PATH_OUTPUT_DIR
        try:
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("打开文件夹失败：%s", exc)

    def _reveal_last_output_location(self) -> None:
        if not self.last_output or not self.last_output.exists():
            messagebox.showwarning("提示", "暂无可定位的输出文件，请先执行填充。")
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.run(["explorer", "/select,", str(self.last_output)], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", str(self.last_output)], check=False)
            else:
                subprocess.run(["xdg-open", str(self.last_output.parent)], check=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("定位输出文件失败：%s", exc)
            messagebox.showerror("错误", f"定位输出文件失败：{exc}")

    def _open_last_output(self) -> None:
        if not self.last_output or not self.last_output.exists():
            messagebox.showwarning("提示", "暂无可打开的输出文件，请先执行填充。")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(self.last_output))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(self.last_output)], check=False)
            else:
                subprocess.run(["xdg-open", str(self.last_output)], check=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("打开输出文件失败：%s", exc)
            messagebox.showerror("错误", f"打开输出文件失败：{exc}")

    def _copy_last_output_path(self) -> None:
        if not self.last_output or not self.last_output.exists():
            messagebox.showwarning("提示", "暂无可复制的输出路径，请先执行填充。")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(str(self.last_output))
            messagebox.showinfo("提示", "已将输出路径复制到剪贴板。")
        except Exception as exc:  # noqa: BLE001
            logger.exception("复制输出路径失败：%s", exc)
            messagebox.showerror("错误", f"复制输出路径失败：{exc}")

    def _copy_last_output_size(self) -> None:
        if not self.last_output or not self.last_output.exists():
            messagebox.showwarning("提示", "暂无可复制的输出大小，请先执行填充。")
            return
        try:
            size_bytes = self.last_output_size_bytes
            if size_bytes is None:
                size_bytes = int(self.last_output.stat().st_size)
            size_kb = max(1, int(size_bytes / 1024))
            size_info = f"{size_bytes} bytes ({size_kb} KB)"
            self.clipboard_clear()
            self.clipboard_append(size_info)
            messagebox.showinfo("提示", f"已复制输出文件大小：{size_info}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("复制输出文件大小失败：%s", exc)
            messagebox.showerror("错误", f"复制输出文件大小失败：{exc}")

    def _update_last_output_status(self, output_path: Optional[Path], processor: Optional[PDFProcessor] = None, engine: Optional[str] = None) -> None:
        try:
            if output_path and output_path.exists():
                self.var_last_output.set(f"最新输出：{output_path}")
                try:
                    size_bytes = int(output_path.stat().st_size)
                    self.last_output_size_bytes = size_bytes
                    size_kb = max(1, int(size_bytes / 1024))
                    self.var_size.set(f"输出文件大小：{size_kb} KB")
                except Exception:
                    self.var_size.set("输出文件大小：-")
                    self.last_output_size_bytes = None
            else:
                self.var_last_output.set("最新输出：-")
                self.var_size.set("输出文件大小：-")
                self.last_output_size_bytes = None

            if processor or engine:
                used_engine = getattr(processor, "last_engine_used", None) if processor else None
                used_engine = used_engine or engine or "-"
                font_info = getattr(processor, "last_font_info", None) if processor else None
                font_info = font_info or "-"
                self.var_engine.set(f"实际引擎：{used_engine}")
                self.var_font.set(f"字体来源：{font_info}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("更新输出状态失败：%s", exc)

    def _set_batch_progress(self, completed: int, total: int) -> None:
        try:
            if total <= 0:
                self.var_batch_progress.set("批量进度：-")
            else:
                self.var_batch_progress.set(f"批量进度：{completed}/{total}")
            self.update_idletasks()
        except Exception as exc:  # noqa: BLE001
            logger.debug("刷新批量进度失败：%s", exc)

    # -----------------------------
    # 字段行管理
    # -----------------------------
    def _add_field_row(self, keyword: str = "", value: str = "") -> None:
        row_frame = tk.Frame(self.fields_container, bg=STYLE_GUI_CARD_BG)
        row_frame.pack(fill=tk.X, padx=4, pady=2)

        kv = tk.StringVar(value=keyword)
        vv = tk.StringVar(value=value)
        e1 = tk.Entry(row_frame, textvariable=kv)
        e2 = tk.Entry(row_frame, textvariable=vv)
        e1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        e2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        def remove_row() -> None:
            row_frame.destroy()
            self.field_rows[:] = [r for r in self.field_rows if r.frame is not row_frame]
            self.var_total.set(f"字段总数：{len(self.field_rows)}")

        tk.Button(row_frame, text="删除", command=remove_row).pack(side=tk.LEFT, padx=4)

        self.field_rows.append(FieldRow(kv, vv, row_frame))
        self.var_total.set(f"字段总数：{len(self.field_rows)}")

    def _load_fields_from_keywords_config(self) -> None:
        try:
            cfg = load_keywords_config()
            if not cfg:
                # 默认两个常见字段
                self._add_field_row("身份证号：", "")
                self._add_field_row("企业名称：", "")
                return
            for k in cfg.keys():
                self._add_field_row(str(k), "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("加载关键词配置失败，将使用默认字段：%s", exc)
            self._add_field_row("身份证号：", "")
            self._add_field_row("企业名称：", "")


__all__ = ["PdfFillerApp"]


