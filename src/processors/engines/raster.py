"""
文件路径：src/processors/engines/raster.py

说明：Pillow 渲染透明 PNG 后由 PyMuPDF 贴回 PDF。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from reportlab.pdfbase import pdfmetrics

from ...components import FileHandler, clamp_baseline, get_logger
from ..layout import wrap_text_lines


logger = get_logger(__name__)


def fill_with_raster(
    base_pdf: Path,
    draw_plan: Dict[int, List["DrawTextLike"]],
    output_pdf: Path,
    *,
    style_text_color_rgb: Tuple[int, int, int],
    style_font_size: int,
    style_line_spacing: float,
    raster_scale: Optional[float],
    use_clamp: bool,
    clamp_margin: float,
    font_file: Optional[Path],
) -> Tuple[str, Optional[str]]:
    """渲染透明 PNG 覆盖并输出。

    返回 (engine_used, font_info)。
    """
    # 延迟导入 Pillow
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"缺少 Pillow 依赖，请安装 pillow：{exc}") from exc

    FileHandler.ensure_parent_writable(output_pdf)
    color_rgb = tuple(v for v in style_text_color_rgb)
    alpha = 255  # 由 GUI/调用侧控制透明度也可；此处保持不透明以清晰可见
    scale = float(raster_scale) if raster_scale and raster_scale > 0 else 1.0

    doc = fitz.open(str(base_pdf))
    for page_index in range(len(doc)):
        page = doc[page_index]
        width_pt = int(page.rect.width * scale)
        height_pt = int(page.rect.height * scale)

        if not draw_plan.get(page_index):
            continue

        img = Image.new("RGBA", (width_pt, height_pt), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 准备字体
        try:
            if font_file and font_file.exists() and font_file.suffix.lower() in {".ttf", ".otf"}:
                font = ImageFont.truetype(str(font_file), int(style_font_size * scale))
                font_info = str(font_file)
            else:
                font = ImageFont.load_default()
                font_info = None
        except Exception:
            font = ImageFont.load_default()
            font_info = None

        # 计算上升线，用于基线对齐
        try:
            ascent, descent = font.getmetrics()  # type: ignore[attr-defined]
        except Exception:
            ascent, descent = int(0.8 * style_font_size * scale), int(0.2 * style_font_size * scale)

        for item in draw_plan.get(page_index, []):
            lines = wrap_text_lines(
                font_name="Helvetica",  # 仅用于度量；Pillow 实际使用 truetype 字体
                font_size=style_font_size,
                text=item.text,
                max_width=item.max_width,
            )
            spacing = item.line_spacing if item.line_spacing is not None else style_line_spacing
            current_y_baseline = item.y
            for line in lines:
                if use_clamp:
                    clamped_x, clamped_y = clamp_baseline(
                        item.x,
                        current_y_baseline,
                        page_width=page.rect.width,
                        page_height=page.rect.height,
                        font_size=style_font_size,
                        margin=clamp_margin,
                    )
                    try:
                        line_w = pdfmetrics.stringWidth(line, "Helvetica", style_font_size)
                    except Exception:
                        line_w = len(line) * float(style_font_size) * 0.6
                    max_x = max(clamp_margin, page.rect.width - clamp_margin - line_w)
                    final_x = min(max(clamp_margin, clamped_x), max_x)
                    x_img = int(final_x * scale)
                    y_img = int((page.rect.height - clamped_y) * scale - ascent)
                else:
                    x_img = int(item.x * scale)
                    y_img = int((page.rect.height - current_y_baseline) * scale - ascent)
                draw.text((x_img, y_img), line, font=font, fill=(color_rgb[0], color_rgb[1], color_rgb[2], alpha))
                current_y_baseline -= spacing

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        page.insert_image(page.rect, stream=buf.getvalue(), keep_proportion=False, overlay=True)

    doc.save(str(output_pdf), deflate=True, clean=True, garbage=4)
    try:
        size_kb = Path(output_pdf).stat().st_size / 1024.0
        logger.info("Raster 输出完成：%s (%.1f KB)", output_pdf, size_kb)
    except Exception:
        pass
    doc.close()
    return ("raster", font_info)


__all__ = ["fill_with_raster"]



