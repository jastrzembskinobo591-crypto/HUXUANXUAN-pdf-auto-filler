"""
文件路径：src/pdf_processor.py

模块职责：
- 核心功能：关键词定位（支持模糊匹配）、文字图层生成（ReportLab）、与原 PDF 合并（PyPDF2）。
- 仅通过 `src/components.py` 进行通用操作（日志、文件、坐标），跨模块变量统一从 `src/variables.py` 引用。

注意：
- 第一阶段默认支持单页定位（page_index 默认 0），代码结构已为多页扩展预留。
- 坐标系差异：pdfplumber 顶左为原点；ReportLab 左下为原点。需做 Y 轴翻转。

变量引用说明（来自 src/variables.py）：
- PATH_TEMP_OVERLAY_PDF, PATH_TEMP_MERGED_PDF, PATH_FONT_FILE
- STYLE_FONT_NAME, STYLE_FONT_NAME_CJK_PREFERRED, STYLE_FONT_SIZE_DEFAULT, STYLE_TEXT_COLOR_RGB,
  STYLE_OFFSET_X_DEFAULT, STYLE_OFFSET_Y_DEFAULT
- CONST_PAGE_INDEX_DEFAULT, CONST_FUZZY_MATCH_THRESHOLD, CONST_CLEAN_TEMP_ON_EXIT
- ERR_KEYWORD_NOT_FOUND, ERR_PAGE_INDEX_OUT_OF_RANGE, ERR_TEXT_LAYER_BUILD_FAILED, ERR_PDF_MERGE_FAILED

组件调用说明（来自 src/components.py）：
- FileHandler（校验与目录确保、输出路径生成）
- get_logger（日志输出）
- right_of_bbox / adjust_coords（坐标计算）
- retry_on_exception（易失败 IO 的重试机制）
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pdfplumber
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from .components import (
    FileHandler,
    get_logger,
    right_of_bbox_baseline,
    adjust_coords,
    clamp_baseline,
    retry_on_exception,
    parse_page_selection,
    split_aliases,
)
from .variables import (
    PATH_TEMP_OVERLAY_PDF,
    PATH_TEMP_MERGED_PDF,
    PATH_FONT_FILE,
    STYLE_FONT_NAME,
    STYLE_FONT_NAME_CJK_PREFERRED,
    STYLE_FONT_NAME_CJK_FALLBACK,
    STYLE_FONT_SIZE_DEFAULT,
    STYLE_TEXT_COLOR_RGB,
    STYLE_OFFSET_X_DEFAULT,
    STYLE_OFFSET_Y_DEFAULT,
    STYLE_LINE_SPACING,
    CONST_PAGE_INDEX_DEFAULT,
    CONST_FUZZY_MATCH_THRESHOLD,
    CONST_CLEAN_TEMP_ON_EXIT,
    CONST_CANDIDATE_CJK_FONT_PATHS,
    STYLE_RASTER_TEXT_ALPHA,
    CONST_RASTER_SCALE,
    CONST_CLAMP_MARGIN_DEFAULT,
    CONST_ENABLE_CLAMP_DEFAULT,
    ERR_KEYWORD_NOT_FOUND,
    ERR_PAGE_INDEX_OUT_OF_RANGE,
    ERR_TEXT_LAYER_BUILD_FAILED,
    ERR_PDF_MERGE_FAILED,
)

# 引擎与布局实现（保持门面 API 不变）
from .processors.layout import wrap_text_lines as _wrap_text_lines_impl
from .processors.engines.reportlab import build_text_layer as _rl_build_text_layer, merge_pdfs as _rl_merge_pdfs
from .processors.engines.pymupdf import fill_with_pymupdf as _engine_pymupdf
from .processors.engines.raster import fill_with_raster as _engine_raster
from .processors.matching import (
    normalize_text as _normalize_text,
    best_fuzzy_window as _best_fuzzy_window,
    bbox_of_chars as _bbox_of_chars,
)


logger = get_logger(__name__)


# 匹配与归一化逻辑由 processors.matching 提供


def _to_reportlab_xy(x: float, y_top_based: float, page_height: float) -> Tuple[float, float]:
    """将 pdfplumber 顶左原点的 Y 值转换为 ReportLab 底左原点的 Y。"""
    return x, page_height - y_top_based


@dataclass
class KeywordHit:
    page_index: int
    bbox_pdfplumber: Tuple[float, float, float, float]
    anchor_reportlab: Tuple[float, float]


@dataclass
class DrawText:
    """绘制文本项，支持按宽度自动换行。

    属性：
        text: 待绘制文本内容。
        x, y: 文本第一行的基线起点（ReportLab 坐标，左下原点）。
        max_width: 最大行宽（pt）；None 表示不限制、不换行。
        line_spacing: 行距（pt）；None 使用全局 STYLE_LINE_SPACING。
    """

    text: str
    x: float
    y: float
    max_width: Optional[float] = None
    line_spacing: Optional[float] = None


class PDFProcessor:
    """PDF 处理器：关键词定位、文字图层生成与合并。

    用法示例：
        processor = PDFProcessor()
        hit = processor.find_keyword_coordinates(pdf_path, "身份证号：", page_index=0)
        output = processor.fill_by_keywords(pdf_path, {"身份证号：": "123456"})
    """

    def __init__(self) -> None:
        self.font_registered_name: Optional[str] = None
        # 运行时信息：用于 GUI/日志展示
        self.last_engine_used: Optional[str] = None
        # 字体信息：可能是字体名或字体文件路径的字符串
        self.last_font_info: Optional[str] = None
        # 最近一次填充统计：total/matched/missing(list)/missing_count
        self.last_fill_stats: Optional[dict] = None
        self._ensure_font_registered()

    # -----------------------------
    # 文本换行工具（委托 processors.layout）
    # -----------------------------
    def _wrap_text_lines(
        self,
        font_name: str,
        font_size: int,
        text: str,
        max_width: Optional[float],
    ) -> List[str]:
        return _wrap_text_lines_impl(font_name=font_name, font_size=font_size, text=text, max_width=max_width)

    def _ensure_font_registered(self) -> None:
        """注册中文字体：优先使用可嵌入的 TTF/OTF，找不到时回退内置 CJK。"""

        def _try_register(path: Path, face_name: str) -> bool:
            try:
                pdfmetrics.registerFont(TTFont(face_name, str(path)))
                self.font_registered_name = face_name
                logger.info("已注册中文字体：%s -> %s", face_name, path)
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("注册字体失败：%s -> %s，原因：%s", face_name, path, exc)
                return False

        # 1) 显式指定字体（仅接受 .ttf/.otf）
        if PATH_FONT_FILE and Path(PATH_FONT_FILE).exists():
            p = Path(PATH_FONT_FILE)
            if p.suffix.lower() in {".ttf", ".otf"}:
                prefer_name = STYLE_FONT_NAME_CJK_PREFERRED or "CustomCJK"
                if _try_register(p, prefer_name):
                    return
            else:
                logger.info("忽略非 TTF/OTF 字体：%s", p)

        # 2) 自动探测：候选路径 + config/fonts 目录
        candidates: List[Path] = []
        for s in CONST_CANDIDATE_CJK_FONT_PATHS:
            ps = Path(s)
            if ps.exists() and ps.suffix.lower() in {".ttf", ".otf"}:
                candidates.append(ps)

        from .variables import PATH_CONFIG_DIR  # 延迟导入避免循环

        fonts_dir = PATH_CONFIG_DIR / "fonts"
        if fonts_dir.exists():
            candidates.extend(sorted(fonts_dir.glob("*.ttf")))
            candidates.extend(sorted(fonts_dir.glob("*.otf")))

        for p in candidates:
            face_name = p.stem
            if _try_register(p, face_name):
                return

        # 3) 回退：内置 CJK 字体（不嵌入）
        try:
            fallback_name = STYLE_FONT_NAME_CJK_FALLBACK or "STSong-Light"
            pdfmetrics.registerFont(UnicodeCIDFont(fallback_name))
            self.font_registered_name = fallback_name
            logger.info("已启用 CJK 回退字体：%s（未嵌入）", fallback_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CJK 回退字体注册失败，将使用英文字体（中文可能显示为方块）：%s", exc)
            self.font_registered_name = None

    # -----------------------------
    # 关键词定位
    # -----------------------------
    def find_keyword_coordinates(
        self,
        pdf_path: Path,
        keyword: str,
        page_index: int = CONST_PAGE_INDEX_DEFAULT,
        fuzzy_threshold: float = CONST_FUZZY_MATCH_THRESHOLD,
    ) -> Optional[KeywordHit]:
        """在指定页面查找关键词，返回包含 pdfplumber bbox 与 ReportLab 锚点的命中信息。

        参数：
            pdf_path: 输入 PDF 路径。
            keyword: 需要定位的关键词（支持包含中文冒号）。
            page_index: 页码（0 基）。
            fuzzy_threshold: 模糊匹配阈值。

        返回：
            KeywordHit 或 None（找不到时返回 None，不抛异常）。
        """
        FileHandler.validate_readable_file(pdf_path)

        with pdfplumber.open(str(pdf_path)) as pdf:
            if page_index < 0 or page_index >= len(pdf.pages):
                logger.warning("[%s] 页面索引越界：%s/%s", ERR_PAGE_INDEX_OUT_OF_RANGE, page_index, len(pdf.pages))
                return None

            page = pdf.pages[page_index]
            chars = page.chars  # 字符级信息，便于精确 bbox

            window = _best_fuzzy_window(chars, keyword, threshold=fuzzy_threshold)
            if window is None:
                logger.warning("[%s] 未找到关键词：%s (page=%s)", ERR_KEYWORD_NOT_FOUND, keyword, page_index)
                return None

            start, end = window
            bbox = _bbox_of_chars(chars, start, end)  # pdfplumber 坐标
            page_width, page_height = float(page.width), float(page.height)

            # 取右侧锚点（使用 bottom 作为基线，仍在 pdfplumber 坐标系）
            anchor_right = right_of_bbox_baseline(bbox, STYLE_OFFSET_X_DEFAULT, STYLE_OFFSET_Y_DEFAULT)
            # 转为 ReportLab 坐标
            anchor_rl = _to_reportlab_xy(anchor_right[0], anchor_right[1], page_height)

            return KeywordHit(page_index=page_index, bbox_pdfplumber=bbox, anchor_reportlab=anchor_rl)

    # -----------------------------
    # 文字图层生成与合并
    # -----------------------------
    def fill_by_keywords(
        self,
        pdf_path: Path,
        keyword_to_value: Dict[str, str],
        per_key_overrides: Optional[Dict[str, Dict[str, float]]] = None,
        output_path: Optional[Path] = None,
        pages: Optional[str] = None,
        fuzzy_threshold: Optional[float] = None,
        engine: str = "pymupdf",
        enable_clamp: Optional[bool] = None,
        clamp_margin: Optional[float] = None,
        raster_scale: Optional[float] = None,
    ) -> Path:
        """根据关键词在 PDF 上填充文字，并生成合并后的新 PDF。

        参数：
            pdf_path: 输入 PDF。
            keyword_to_value: 键为关键词、值为需要填充的文本。
            per_key_overrides: 可选覆盖项，如 {"身份证号：": {"page": 0, "offset_x": 60}}。
            output_path: 输出文件路径；不提供时自动生成到 output 目录。
            pages: 页选择（如 "all" 或 "1,3-5"，1 基）。
            fuzzy_threshold: 模糊匹配阈值（0~1）；None 表示使用全局默认。

        返回：
            最终输出 PDF 路径。
        """
        FileHandler.validate_readable_file(pdf_path)
        FileHandler.ensure_project_dirs()

        # 读取页面尺寸
        with pdfplumber.open(str(pdf_path)) as pdf:
            page_sizes = [(float(p.width), float(p.height)) for p in pdf.pages]
            total_pages = len(pdf.pages)

        # 解析全局页选择（仅当提供 pages 参数时生效；未提供则保持向后兼容，仅默认第 0 页）
        selected_pages_global: Optional[List[int]] = None
        if pages:
            selected = parse_page_selection(pages, total_pages=total_pages, one_based=True)
            selected_pages_global = selected if selected else list(range(total_pages))
        # 归一化阈值
        try:
            _fuzzy_thr = float(fuzzy_threshold) if (fuzzy_threshold is not None) else float(CONST_FUZZY_MATCH_THRESHOLD)
        except Exception:
            _fuzzy_thr = float(CONST_FUZZY_MATCH_THRESHOLD)


        # 计算每个需要绘制的元素位置
        per_key_overrides = per_key_overrides or {}
        # draw_plan: {page_index: [DrawText, ...]}
        draw_plan: Dict[int, List[DrawText]] = {}
        # 统计：输入有效字段数、命中/未命中列表
        total_considered = 0
        matched_keys: List[str] = []
        missing_keys: List[str] = []

        def _resolve_override_for_key(k: str) -> Tuple[Optional[str], Dict[str, float]]:
            """依据输入键解析对应的覆盖配置。

            规则：
            - 优先精确匹配 `per_key_overrides` 的键；
            - 否则将输入键按别名分隔（split_aliases）后，与任一覆盖项的 `aliases` 列表求交集，命中则返回其规范名与配置；
            - 若均未命中，返回 (None, {})。
            """
            # 1) 精确命中
            if k in per_key_overrides:
                return k, per_key_overrides.get(k, {})

            # 2) 按别名求交集命中
            try:
                k_aliases = split_aliases(k)
            except Exception:
                k_aliases = [str(k)]

            for canon, cfg in per_key_overrides.items():
                try:
                    aliases = cfg.get("aliases") if isinstance(cfg, dict) else None
                    if not isinstance(aliases, list):
                        continue
                    # 归一化比较（字符串）
                    alias_set = {str(a) for a in aliases}
                    if any(ka in alias_set for ka in k_aliases):
                        return canon, cfg
                except Exception:
                    continue
            return None, {}

        for key, value in keyword_to_value.items():
            if not value:
                continue
            total_considered += 1
            canon_key, ov = _resolve_override_for_key(key)
            page_index = int(ov.get("page", CONST_PAGE_INDEX_DEFAULT))
            offset_x = float(ov.get("offset_x", STYLE_OFFSET_X_DEFAULT))
            offset_y = float(ov.get("offset_y", STYLE_OFFSET_Y_DEFAULT))
            max_width = float(ov.get("max_width")) if "max_width" in ov else None
            line_spacing = float(ov.get("line_spacing")) if "line_spacing" in ov else None

            # 生成候选关键词：输入内的别名 + 配置中的别名（若有）
            candidates = []
            try:
                candidates.extend(split_aliases(key))
            except Exception:
                candidates.append(str(key))
            try:
                aliases_from_cfg = ov.get("aliases") if isinstance(ov, dict) else None
                if isinstance(aliases_from_cfg, list):
                    for a in aliases_from_cfg:
                        if a not in candidates:
                            candidates.append(a)
                # 将规范名也作为候选（若存在）
                if canon_key and canon_key not in candidates:
                    candidates.append(canon_key)
            except Exception:
                pass

            hit: Optional[KeywordHit] = None
            # 优先使用每键覆盖页；否则在选定页集合中依序搜索（若未提供 pages，则保持仅搜索默认页）
            if "page" in ov:
                # 指定页：在该页上依序尝试候选关键词
                for cand in candidates:
                    hit = self.find_keyword_coordinates(pdf_path, cand, page_index=page_index, fuzzy_threshold=_fuzzy_thr)
                    if hit:
                        break
            else:
                candidate_pages = selected_pages_global if selected_pages_global is not None else [page_index]
                found = False
                for p in candidate_pages:
                    for cand in candidates:
                        hit = self.find_keyword_coordinates(pdf_path, cand, page_index=p, fuzzy_threshold=_fuzzy_thr)
                        if hit:
                            page_index = p
                            found = True
                            break
                    if found:
                        break
            if not hit:
                logger.warning("[%s] 关键词未定位：%s", ERR_KEYWORD_NOT_FOUND, key)
                missing_keys.append(str(key))
                continue

            # 在锚点基础上应用覆盖偏移
            x_final, y_final = adjust_coords(
                hit.anchor_reportlab[0],
                hit.anchor_reportlab[1],
                offset_x=offset_x - STYLE_OFFSET_X_DEFAULT,
                offset_y=offset_y - STYLE_OFFSET_Y_DEFAULT,
            )
            draw_plan.setdefault(page_index, []).append(
                DrawText(text=str(value), x=x_final, y=y_final, max_width=max_width, line_spacing=line_spacing)
            )
            matched_keys.append(str(key))

        if not draw_plan:
            logger.warning("[%s] 未产生任何绘制计划，可能全部关键词未匹配", ERR_TEXT_LAYER_BUILD_FAILED)

        # 记录统计信息供调用方展示
        try:
            self.last_fill_stats = {
                "total": int(total_considered),
                "matched": int(len(matched_keys)),
                "missing_count": int(len(missing_keys)),
                "missing": list(missing_keys),
                "matched_keys": list(matched_keys),
            }
        except Exception:
            self.last_fill_stats = None

        # 输出路径
        if output_path is None:
            out = FileHandler.timestamped_output_path(pdf_path)
        else:
            out = output_path

        # 钳制与边距配置（允许外部覆盖）
        use_clamp = CONST_ENABLE_CLAMP_DEFAULT if enable_clamp is None else bool(enable_clamp)
        use_margin = CONST_CLAMP_MARGIN_DEFAULT if clamp_margin is None else float(clamp_margin)

        # 引擎选择
        if engine == "pymupdf":
            # 由内部决定是否回退，内部会设置 last_engine_used/last_font_info
            self._fill_with_pymupdf(pdf_path, draw_plan, out, use_clamp=use_clamp, clamp_margin=use_margin)
            return out

        if engine == "raster":
            self._fill_with_raster(
                pdf_path,
                draw_plan,
                out,
                use_clamp=use_clamp,
                clamp_margin=use_margin,
                raster_scale=raster_scale,
            )
            # 记录运行时信息
            self.last_engine_used = "raster"
            return out

        # 默认回退：reportlab 生成 overlay + PyPDF2 合并
        self._build_text_layer(page_sizes, draw_plan, PATH_TEMP_OVERLAY_PDF, use_clamp=use_clamp, clamp_margin=use_margin)
        self._merge_pdfs(pdf_path, PATH_TEMP_OVERLAY_PDF, out)
        # 记录运行时信息（合成路径）
        self.last_engine_used = "reportlab"
        self.last_font_info = self.font_registered_name
        if CONST_CLEAN_TEMP_ON_EXIT:
            try:
                PATH_TEMP_OVERLAY_PDF.unlink(missing_ok=True)
            except Exception:
                logger.debug("临时文件清理失败：%s", PATH_TEMP_OVERLAY_PDF)
        return out

    @retry_on_exception()
    def _build_text_layer(
        self,
        page_sizes: List[Tuple[float, float]],
        draw_plan: Dict[int, List["DrawText"]],
        overlay_path: Path,
        *,
        use_clamp: bool = True,
        clamp_margin: float = CONST_CLAMP_MARGIN_DEFAULT,
    ) -> None:
        font_name = self.font_registered_name or STYLE_FONT_NAME
        _rl_build_text_layer(
            page_sizes,
            draw_plan,
            overlay_path,
            font_name=font_name,
            style_text_color_rgb=STYLE_TEXT_COLOR_RGB,
            style_font_size=STYLE_FONT_SIZE_DEFAULT,
            style_line_spacing=STYLE_LINE_SPACING,
            use_clamp=use_clamp,
            clamp_margin=clamp_margin,
        )

    @retry_on_exception()
    def _merge_pdfs(self, base_pdf: Path, overlay_pdf: Path, output_pdf: Path) -> None:
        _rl_merge_pdfs(base_pdf, overlay_pdf, output_pdf)

    # -----------------------------
    # PyMuPDF 引擎：直接在原 PDF 上写入文本
    # -----------------------------
    def _fill_with_pymupdf(
        self,
        base_pdf: Path,
        draw_plan: Dict[int, List["DrawText"]],
        output_pdf: Path,
        *,
        use_clamp: bool = True,
        clamp_margin: float = CONST_CLAMP_MARGIN_DEFAULT,
    ) -> None:
        """使用 PyMuPDF 在 PDF 上直接绘制文本，内嵌字体文件。

        注意：这里使用的坐标与 ReportLab 相同（左下为原点），传给 insert_text 作为文本基线点。
        若系统未提供字体文件，将由 PyMuPDF 选择默认字体（英文正常，中文可能为空）。
        """
        # 选择字体文件（优先 PATH_FONT_FILE，其次候选列表）
        preferred_fontname = (STYLE_FONT_NAME_CJK_PREFERRED or "SimHei").strip() or "SimHei"
        font_file: Optional[Path] = None
        if PATH_FONT_FILE and Path(PATH_FONT_FILE).exists() and Path(PATH_FONT_FILE).suffix.lower() in {".ttf", ".otf"}:
            font_file = Path(PATH_FONT_FILE)
        else:
            for s in CONST_CANDIDATE_CJK_FONT_PATHS:
                p = Path(s)
                if p.exists() and p.suffix.lower() in {".ttf", ".otf"}:
                    font_file = p
                    break

        engine_used, font_info = _engine_pymupdf(
            base_pdf,
            draw_plan,
            output_pdf,
            style_text_color_rgb=STYLE_TEXT_COLOR_RGB,
            style_font_size=STYLE_FONT_SIZE_DEFAULT,
            style_line_spacing=STYLE_LINE_SPACING,
            use_clamp=use_clamp,
            clamp_margin=clamp_margin,
            font_file=font_file,
            preferred_fontname=preferred_fontname,
            temp_overlay_pdf=PATH_TEMP_OVERLAY_PDF,
            clean_temp_on_exit=bool(CONST_CLEAN_TEMP_ON_EXIT),
        )
        self.last_engine_used = engine_used
        self.last_font_info = font_info

    # -----------------------------
    # Raster 引擎：Pillow 渲染透明 PNG 覆盖
    # -----------------------------
    def _fill_with_raster(
        self,
        base_pdf: Path,
        draw_plan: Dict[int, List["DrawText"]],
        output_pdf: Path,
        *,
        use_clamp: bool = True,
        clamp_margin: float = CONST_CLAMP_MARGIN_DEFAULT,
        raster_scale: Optional[float] = None,
    ) -> None:
        """使用 Pillow 将文本渲染为透明 PNG，并通过 PyMuPDF 贴回原 PDF。

        说明：
        - 采用 1pt=1px（CONST_RASTER_SCALE 可调整倍率），坐标保持与 ReportLab 一致。
        - 文字位置以基线 y 为准，Pillow 需要减去字体上升线（ascent）得到绘制起点。
        - 优点：阅读器 100% 一致显示；缺点：文字不可选中复制。
        """
        # 选择字体文件（优先 PATH_FONT_FILE，其次候选列表）
        font_file: Optional[Path] = None
        if PATH_FONT_FILE and Path(PATH_FONT_FILE).exists() and Path(PATH_FONT_FILE).suffix.lower() in {".ttf", ".otf"}:
            font_file = Path(PATH_FONT_FILE)
        else:
            for s in CONST_CANDIDATE_CJK_FONT_PATHS:
                p = Path(s)
                if p.exists() and p.suffix.lower() in {".ttf", ".otf"}:
                    font_file = p
                    break

        engine_used, font_info = _engine_raster(
            base_pdf,
            draw_plan,
            output_pdf,
            style_text_color_rgb=STYLE_TEXT_COLOR_RGB,
            style_font_size=STYLE_FONT_SIZE_DEFAULT,
            style_line_spacing=STYLE_LINE_SPACING,
            raster_scale=raster_scale if raster_scale is not None else float(CONST_RASTER_SCALE or 1.0),
            use_clamp=use_clamp,
            clamp_margin=clamp_margin,
            font_file=font_file,
        )
        self.last_engine_used = engine_used
        self.last_font_info = font_info or "default"


__all__ = [
    "PDFProcessor",
    "KeywordHit",
]


