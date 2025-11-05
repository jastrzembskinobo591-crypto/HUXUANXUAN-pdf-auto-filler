"""
文件路径：src/processors/engines/pymupdf.py

说明：PyMuPDF 直接绘制文本的实现；若无法内嵌字体则回退到 ReportLab 合成路径。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import pdfplumber
from reportlab.pdfbase import pdfmetrics

from ...components import FileHandler, clamp_baseline, get_logger
from ..layout import wrap_text_lines
from .reportlab import build_text_layer, merge_pdfs


logger = get_logger(__name__)


def fill_with_pymupdf(
    base_pdf: Path,
    draw_plan: Dict[int, List["DrawTextLike"]],
    output_pdf: Path,
    *,
    style_text_color_rgb: Tuple[int, int, int],
    style_font_size: int,
    style_line_spacing: float,
    use_clamp: bool,
    clamp_margin: float,
    font_file: Optional[Path],
    preferred_fontname: str,
    temp_overlay_pdf: Path,
    clean_temp_on_exit: bool,
) -> Tuple[str, Optional[str]]:
    """在 PDF 上直接绘制文本；必要时回退 ReportLab 合成路径。

    返回 (engine_used, font_info)。
    """
    FileHandler.ensure_parent_writable(output_pdf)
    try:
        doc = fitz.open(str(base_pdf))
        color = tuple(v / 255.0 for v in style_text_color_rgb)

        fontname_to_use: Optional[str] = None
        if font_file and font_file.exists() and font_file.suffix.lower() in {".ttf", ".otf"}:
            try:
                doc.insert_font(fontname=preferred_fontname, file=str(font_file))
                fontname_to_use = preferred_fontname
                logger.info("PyMuPDF 已内嵌字体：%s -> %s", preferred_fontname, font_file)
            except Exception as exc:  # noqa: BLE001
                logger.warning("PyMuPDF 字体内嵌失败，将尝试回退：%s", exc)

        # 无法内嵌：回退到 ReportLab 合成路径
        if fontname_to_use is None:
            try:
                page_sizes = [(float(p.rect.width), float(p.rect.height)) for p in doc]
            except Exception:  # noqa: BLE001
                page_sizes = []
            finally:
                try:
                    doc.close()
                except Exception:
                    pass

            if not page_sizes:
                with pdfplumber.open(str(base_pdf)) as pdf:
                    page_sizes = [(float(p.width), float(p.height)) for p in pdf.pages]
            build_text_layer(
                page_sizes,
                draw_plan,
                temp_overlay_pdf,
                font_name=preferred_fontname,  # 仅用于度量；ReportLab 使用已注册字体或默认
                style_text_color_rgb=style_text_color_rgb,
                style_font_size=style_font_size,
                style_line_spacing=style_line_spacing,
                use_clamp=use_clamp,
                clamp_margin=clamp_margin,
            )
            merge_pdfs(base_pdf, temp_overlay_pdf, output_pdf)
            if clean_temp_on_exit:
                try:
                    temp_overlay_pdf.unlink(missing_ok=True)
                except Exception:
                    pass
            return ("reportlab", str(font_file) if font_file else preferred_fontname)

        # 直接绘制路径
        for page_index in range(len(doc)):
            page = doc[page_index]
            for item in draw_plan.get(page_index, []):
                lines = wrap_text_lines(
                    font_name=preferred_fontname,
                    font_size=style_font_size,
                    text=item.text,
                    max_width=item.max_width,
                )
                spacing = item.line_spacing if item.line_spacing is not None else style_line_spacing
                current_y = item.y
                for line in lines:
                    if use_clamp:
                        clamped_x, clamped_y = clamp_baseline(
                            item.x,
                            current_y,
                            page_width=page.rect.width,
                            page_height=page.rect.height,
                            font_size=style_font_size,
                            margin=clamp_margin,
                        )
                        try:
                            line_w = pdfmetrics.stringWidth(line, preferred_fontname, style_font_size)
                        except Exception:
                            line_w = len(line) * float(style_font_size) * 0.6
                        max_x = max(clamp_margin, page.rect.width - clamp_margin - line_w)
                        final_x = min(max(clamp_margin, clamped_x), max_x)
                        y_baseline = page.rect.height - clamped_y
                        draw_x, draw_y_baseline = final_x, y_baseline
                    else:
                        draw_x, draw_y_baseline = item.x, page.rect.height - current_y
                    page.insert_text((draw_x, draw_y_baseline), line, fontsize=style_font_size, fontname=fontname_to_use, color=color)
                    current_y -= spacing

        doc.save(str(output_pdf), deflate=True, clean=True, garbage=4)
        try:
            size_kb = Path(output_pdf).stat().st_size / 1024.0
            logger.info("PyMuPDF 输出完成：%s (%.1f KB)", output_pdf, size_kb)
        except Exception:
            pass
        doc.close()
        return ("pymupdf", str(font_file) if font_file else preferred_fontname)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"使用 PyMuPDF 写入失败: {exc}") from exc


__all__ = ["fill_with_pymupdf"]



