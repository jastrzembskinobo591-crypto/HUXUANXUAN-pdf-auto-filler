"""
文件路径：src/processors/engines/reportlab.py

说明：ReportLab 路径的图层生成与 PyPDF2 合并。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter

from ...components import FileHandler, clamp_baseline, get_logger
from ..layout import wrap_text_lines


logger = get_logger(__name__)


def build_text_layer(
    page_sizes: List[Tuple[float, float]],
    draw_plan: Dict[int, List["DrawTextLike"]],
    overlay_path: Path,
    *,
    font_name: str,
    style_text_color_rgb: Tuple[int, int, int],
    style_font_size: int,
    style_line_spacing: float,
    use_clamp: bool,
    clamp_margin: float,
) -> None:
    """使用 ReportLab 生成仅含文字标注的图层 PDF。"""
    FileHandler.ensure_parent_writable(overlay_path)
    c = canvas.Canvas(str(overlay_path))

    c.setFillColorRGB(*(v / 255.0 for v in style_text_color_rgb))

    for page_index, (w, h) in enumerate(page_sizes):
        c.setPageSize((w, h))
        for item in draw_plan.get(page_index, []):
            c.setFont(font_name, style_font_size)
            lines = wrap_text_lines(
                font_name=font_name,
                font_size=style_font_size,
                text=item.text,
                max_width=item.max_width,
            )
            current_y = item.y
            spacing = item.line_spacing if item.line_spacing is not None else style_line_spacing
            for line in lines:
                if use_clamp:
                    clamped_x, clamped_y = clamp_baseline(
                        item.x,
                        current_y,
                        page_width=w,
                        page_height=h,
                        font_size=style_font_size,
                        margin=clamp_margin,
                    )
                    try:
                        line_w = pdfmetrics.stringWidth(line, font_name, style_font_size)
                    except Exception:
                        line_w = len(line) * float(style_font_size) * 0.6
                    max_x = max(clamp_margin, w - clamp_margin - line_w)
                    final_x = min(max(clamp_margin, clamped_x), max_x)
                    draw_x, draw_y = final_x, clamped_y
                else:
                    draw_x, draw_y = item.x, current_y
                c.drawString(draw_x, draw_y, line)
                current_y -= spacing
        c.showPage()

    c.save()


def merge_pdfs(base_pdf: Path, overlay_pdf: Path, output_pdf: Path) -> None:
    """将 overlay 覆盖合并到 base 上，输出到 output_pdf。"""
    FileHandler.ensure_parent_writable(output_pdf)
    base_reader = PdfReader(str(base_pdf))
    overlay_reader = PdfReader(str(overlay_pdf))

    writer = PdfWriter()
    for i, page in enumerate(base_reader.pages):
        base_page = page
        if i < len(overlay_reader.pages):
            overlay_page = overlay_reader.pages[i]
            base_page.merge_page(overlay_page)  # PyPDF2 3.x API
        writer.add_page(base_page)

    with open(output_pdf, "wb") as f:  # noqa: P103
        writer.write(f)


__all__ = ["build_text_layer", "merge_pdfs"]



