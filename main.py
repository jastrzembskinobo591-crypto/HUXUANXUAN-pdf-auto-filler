"""
文件路径：main.py

命令行入口：
- 功能：读取输入 PDF，按关键词填充文字，合并输出到 output 目录。
- 依赖：`src/pdf_processor.py`、`src/data_handler.py`、`src/components.py`、`src/variables.py`。

快速使用示例：
    # 1) 若没有示例 PDF，本程序可自动生成一份包含关键词的示例 PDF
    python main.py --make-example

    # 2) 使用关键词-值 JSON 进行填充（示例）
    python main.py --input examples/blank_contract.pdf --data-json examples/data.json

    # 3) 直接在命令行键入键值对（可多次传入 --kv）
    python main.py --input examples/blank_contract.pdf --kv "身份证号：=1234567890" --kv "企业名称：=某某科技"

运行说明（如何替换文件路径、修改填充信息）：
- 替换输入文件：使用 --input 指定你的 PDF 路径，例如 --input D:/docs/a.pdf
- 自定义填充值：
  - 方式 A：使用 --kv 多次传入（格式：关键词=值），如 --kv "法人姓名：=张三"
  - 方式 B：提供 JSON 文件，结构为 {"关键词": "值"}，用 --data-json 指定路径
- 修改填充位置：在 config/keywords.json 中调整对应关键词的 offset_x/offset_y 或 page 字段

变量引用说明（来自 src/variables.py）：
- PATH_DEFAULT_INPUT_PDF, PATH_EXAMPLES_DIR, CONST_ENCODING, PATH_FONT_FILE, STYLE_FONT_NAME_CJK_PREFERRED

组件调用说明（来自 src/components.py / src/data_handler.py / src/pdf_processor.py）：
- get_logger, FileHandler.ensure_project_dirs/validate_readable_file/timestamped_output_path
- load_keywords_config, sanitize_input_data
- PDFProcessor.fill_by_keywords / find_keyword_coordinates
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

from src.components import FileHandler, get_logger
from src.data_handler import (
    load_keywords_config,
    sanitize_input_data,
    load_batch_json,
    load_batch_csv,
    load_templates_index,
    infer_template_id_from_filename,
)
from src.pdf_processor import PDFProcessor
from src.variables import (
    PATH_DEFAULT_INPUT_PDF,
    PATH_EXAMPLES_DIR,
    CONST_ENCODING,
    PATH_FONT_FILE,
    STYLE_FONT_NAME_CJK_PREFERRED,
    CONST_INDEX_PAD_WIDTH_DEFAULT,
    CONST_DEFAULT_OUTPUT_SUFFIX,
    CONST_LOG_PYMUPDF_CAPABILITIES_ON_STARTUP,
    CONST_BATCH_AUTO_TEMPLATE_DEFAULT,
    CONST_FUZZY_MATCH_THRESHOLD,
)


logger = get_logger(__name__)


def _log_runtime_capabilities() -> None:
    """启动时输出运行环境信息：PyMuPDF 版本与 insert_font 可用性。

    - 变量引用：CONST_LOG_PYMUPDF_CAPABILITIES_ON_STARTUP
    - 组件调用：get_logger
    """
    if not CONST_LOG_PYMUPDF_CAPABILITIES_ON_STARTUP:
        return
    try:
        # 版本信息：优先用 importlib.metadata 获取精确版本
        try:
            import importlib.metadata as im  # Python 3.8+

            version = im.version("PyMuPDF")
        except Exception:
            version = None
        try:
            import fitz  # type: ignore

            ver_doc = getattr(fitz, "__doc__", "") or ""
            if not version and ver_doc:
                # __doc__ 形如 "PyMuPDF 1.23.x"，取第一段数字
                parts = ver_doc.split()
                version = next((p for p in parts if any(ch.isdigit() for ch in p)), None)
            # 能力检测：insert_font 是否可用
            has_insert_font = hasattr(getattr(fitz, "Document", object), "insert_font")
            logger.info(
                "运行环境：PyMuPDF version=%s, Document.insert_font=%s",
                (version or "unknown"),
                has_insert_font,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("无法检测 PyMuPDF 运行环境：%s", exc)

        # 字体与度量来源提示（不依赖第三方 lib 的探测）
        try:
            from src.components import probe_available_cjk_fonts, pick_preferred_cjk_font
            from src.variables import PATH_FONT_FILE

            preferred = pick_preferred_cjk_font()
            candidates = probe_available_cjk_fonts()
            path_override = (str(PATH_FONT_FILE) if PATH_FONT_FILE else None)
            logger.info(
                "字体探测：override=%s, preferred=%s, candidates=%s, metrics=ReportLab.pdfmetrics",
                path_override,
                (str(preferred) if preferred else "None"),
                [str(p) for p in candidates[:5]] + (["..."] if len(candidates) > 5 else []),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("字体探测失败：%s", exc)
    except Exception:
        # 启动日志不应影响正常功能
        pass

def _ensure_example_pdf() -> Path:
    """若 `examples/blank_contract.pdf` 不存在，则生成用于测试的示例 PDF。

    生成内容：页面左上区域绘制“身份证号：”“企业名称：”两个关键词，便于关键词定位测试。
    """
    from reportlab.pdfgen import canvas  # 延迟导入以加快 CLI 启动
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    examples_dir = PATH_EXAMPLES_DIR
    examples_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = examples_dir / "blank_contract.pdf"
    if pdf_path.exists():
        return pdf_path

    c = canvas.Canvas(str(pdf_path))
    c.setPageSize((595.28, 841.89))  # A4
    # 注册并优先使用中文字体，确保关键词可被 pdfplumber 识别
    font_name = "Helvetica"
    try:
        if PATH_FONT_FILE and PATH_FONT_FILE.exists():
            preferred = STYLE_FONT_NAME_CJK_PREFERRED or "SimSun"
            pdfmetrics.registerFont(TTFont(preferred, str(PATH_FONT_FILE)))
            font_name = preferred
            logger.info("示例PDF使用中文字体：%s -> %s", preferred, PATH_FONT_FILE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("中文字体注册失败，将使用 Helvetica：%s", exc)
    c.setFont(font_name, 12)
    # 在靠近左上方绘制关键词（注意：ReportLab 原点在左下）
    c.drawString(72, 800, "身份证号：")
    c.drawString(72, 770, "企业名称：")
    c.drawString(72, 740, "联系电话：")
    c.save()
    logger.info("已生成示例 PDF：%s", pdf_path)
    return pdf_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDF 自动填充工具（关键词定位 + 坐标写入）")
    parser.add_argument("--input", type=Path, default=PATH_DEFAULT_INPUT_PDF, help="输入 PDF 路径")
    parser.add_argument("--output", type=Path, default=None, help="输出 PDF 路径（可省略，自动生成）")
    parser.add_argument("--output-prefix", dest="output_prefix", type=str, default=None, help="输出文件名前缀（覆盖输入文件名 stem）")
    parser.add_argument("--data-json", dest="data_json", type=Path, default=None, help="包含 关键词->值 的 JSON 文件")
    parser.add_argument("--batch-json", dest="batch_json", type=Path, default=None, help="批量 JSON，数组或包含 records 数组")
    parser.add_argument("--batch-csv", dest="batch_csv", type=Path, default=None, help="批量 CSV，首行为表头，表头即关键词")
    parser.add_argument("--batch-output-dir", dest="batch_output_dir", type=Path, default=None, help="批量输出目录（默认 output/）")
    parser.add_argument("--index-width", dest="index_width", type=int, default=None, help="批量输出序号零填充宽度，默认使用全局配置")
    parser.add_argument("--template-id", dest="template_id", type=str, default=None, help="模板 ID（从 config/templates.json 选择关键词配置）")
    parser.add_argument("--keywords-json", dest="keywords_json", type=Path, default=None, help="显式指定关键词配置 JSON（覆盖模板与默认值）")
    parser.add_argument("--kv", action="append", default=None, help="直接在命令行提供键值对，如 --kv '身份证号：=123'，可重复")
    parser.add_argument("--pages", type=str, default=None, help="页选择：'all' 或 '1,3-5'（1 基）")
    parser.add_argument("--fuzzy-threshold", dest="fuzzy_threshold", type=float, default=None, help=f"模糊匹配阈值（0~1），默认 {CONST_FUZZY_MATCH_THRESHOLD}")
    parser.add_argument("--engine", type=str, choices=["pymupdf", "reportlab", "raster"], default="pymupdf", help="渲染引擎：pymupdf/reportlab/raster")
    parser.add_argument("--batch-auto-template", dest="batch_auto_template", action="store_true", help="批量模式：逐条记录按输入文件名自动匹配模板ID（当未显式提供 --keywords-json/--template-id 时生效）")
    parser.add_argument("--make-example", action="store_true", help="若示例 PDF 不存在则生成一份示例合同")
    parser.add_argument("--gui", action="store_true", help="启动图形界面（tkinter）")
    return parser.parse_args()


def build_data_from_args(args: argparse.Namespace) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    if args.data_json:
        content = args.data_json.read_text(encoding=CONST_ENCODING)
        import json

        data = json.loads(content)
        if not isinstance(data, dict):
            raise SystemExit("--data-json 文件内容必须是字典 {关键词: 值}")
        pairs.update({str(k): str(v) for k, v in data.items()})

    if args.kv:
        for item in args.kv:
            if "=" not in item:
                raise SystemExit("--kv 需为 '关键词=值' 格式")
            k, v = item.split("=", 1)
            pairs[str(k)] = str(v)

    return sanitize_input_data(pairs)


def main() -> None:
    _log_runtime_capabilities()
    args = parse_args()
    if args.gui:
        # 延迟导入以加快 CLI 冷启动
        from src.ui import PdfFillerApp

        app = PdfFillerApp()
        app.mainloop()
        return
    if args.make_example:
        pdf_path = _ensure_example_pdf()
        print(f"示例 PDF 已就绪：{pdf_path}")
        return

    # 若输入 PDF 不存在，自动尝试创建示例 PDF
    input_pdf: Path = args.input
    if not input_pdf.exists():
        logger.warning("输入 PDF 不存在：%s，将生成示例 PDF 以便测试。", input_pdf)
        input_pdf = _ensure_example_pdf()

    # 解析关键词配置路径（支持：显式文件 / 模板ID / 按输入文件名自动匹配模板ID）
    kw_config_path: Path | None = None
    if args.keywords_json is not None:
        kw_config_path = args.keywords_json
    elif args.template_id is not None:
        mapping = load_templates_index()
        if args.template_id in mapping:
            kw_config_path = Path(mapping[args.template_id])
            logger.info("使用模板ID=%s 的关键词配置：%s", args.template_id, kw_config_path)
        else:
            logger.warning("未在 templates.json 中找到模板ID=%s，将使用默认配置", args.template_id)
    else:
        # 未显式指定时，尝试基于输入 PDF 文件名自动匹配模板ID
        mapping = load_templates_index()
        auto_tid = infer_template_id_from_filename(input_pdf)
        if auto_tid and auto_tid in mapping:
            kw_config_path = Path(mapping[auto_tid])
            logger.info("已基于文件名自动匹配模板ID=%s，使用配置：%s", auto_tid, kw_config_path)

    # 批量模式优先
    if args.batch_json or args.batch_csv:
        if args.output is not None:
            logger.warning("批量模式下将忽略 --output，改用按序号自动生成多个输出文件")
        records: List[Dict[str, str]] = []
        if args.batch_json:
            records = load_batch_json(args.batch_json)
        if args.batch_csv:
            records = load_batch_csv(args.batch_csv)
        if not records:
            raise SystemExit("未从批量数据中解析到任何记录")

        # 模板索引（用于模板ID -> 路径）
        templates_mapping = load_templates_index()

        # 全局默认关键词配置（偏移等覆盖），供未逐条覆盖时使用
        default_kw_config_path = kw_config_path
        default_kw_overrides = load_keywords_config(default_kw_config_path)

        # 批量自动匹配开关（优先级低于显式 --keywords-json/--template-id）
        use_batch_auto_template = bool(getattr(args, "batch_auto_template", False) or False)
        if not use_batch_auto_template:
            # 若 CLI 未显式开启，回退到全局常量
            use_batch_auto_template = bool(CONST_BATCH_AUTO_TEMPLATE_DEFAULT)

        # 输出目录可选重定向
        if args.batch_output_dir:
            args.batch_output_dir.mkdir(parents=True, exist_ok=True)

        from src.components import FileHandler as _FH  # 延迟以避免循环

        processor = PDFProcessor()
        outputs: List[Path] = []
        for i, record in enumerate(records, start=1):
            if not record:
                logger.info("第 %s 条为空记录，已跳过", i)
                continue
            # 每条记录允许保留键覆盖：__input_pdf / __template_id / __keywords_json
            raw_input_hint = record.get("__input_pdf")
            local_input_pdf = input_pdf
            if raw_input_hint:
                try:
                    cand = Path(str(raw_input_hint))
                    if cand.exists() and cand.is_file():
                        local_input_pdf = cand
                    else:
                        logger.warning("第 %s 条记录的 __input_pdf 不存在或不可用：%s，已回退到全局输入", i, raw_input_hint)
                except Exception:
                    logger.warning("第 %s 条记录的 __input_pdf 无法解析：%s，已回退到全局输入", i, raw_input_hint)

            # 逐条选择关键词配置路径（优先级：全局显式 > 记录覆盖 > 批量自动匹配 > 全局默认/自动）
            rec_kw_config_path = default_kw_config_path
            global_explicit = (args.keywords_json is not None) or (args.template_id is not None)
            if not global_explicit:
                # 记录层覆盖
                if record.get("__keywords_json"):
                    try:
                        rec_kw = Path(str(record.get("__keywords_json")))
                        if rec_kw.exists():
                            rec_kw_config_path = rec_kw
                            logger.info("第 %s 条记录使用 __keywords_json：%s", i, rec_kw)
                    except Exception:
                        logger.warning("第 %s 条记录的 __keywords_json 无法解析，忽略", i)
                elif record.get("__template_id"):
                    rec_tid = str(record.get("__template_id")).strip()
                    if rec_tid in templates_mapping:
                        rec_kw_config_path = Path(templates_mapping[rec_tid])
                        logger.info("第 %s 条记录使用 __template_id=%s -> %s", i, rec_tid, rec_kw_config_path)
                    else:
                        logger.warning("第 %s 条记录提供的 __template_id=%s 未在 templates.json 中找到，忽略", i, rec_tid)
                elif use_batch_auto_template:
                    # 自动匹配：按逐条输入 PDF 文件名推断模板ID
                    auto_tid = infer_template_id_from_filename(local_input_pdf)
                    if auto_tid and auto_tid in templates_mapping:
                        rec_kw_config_path = Path(templates_mapping[auto_tid])
                        logger.info("第 %s 条记录自动匹配模板ID=%s，使用配置：%s", i, auto_tid, rec_kw_config_path)

            # 加载该记录的关键词覆盖
            kw_overrides = load_keywords_config(rec_kw_config_path)

            # 过滤保留键后再绘制
            clean_record = {k: v for k, v in record.items() if not str(k).startswith("__")}

            out_path = _FH.indexed_output_path(
                local_input_pdf,
                index=i,
                pad=(args.index_width if args.index_width is not None else CONST_INDEX_PAD_WIDTH_DEFAULT),
                prefix=args.output_prefix,
            )
            if args.batch_output_dir:
                out_path = args.batch_output_dir / out_path.name
            result = processor.fill_by_keywords(
                local_input_pdf,
                clean_record,
                per_key_overrides=kw_overrides,
                output_path=out_path,
                pages=args.pages,
                fuzzy_threshold=getattr(args, "fuzzy_threshold", None),
                engine=args.engine,
            )
            outputs.append(result)
            # 每条记录输出未命中统计（不阻断）
            try:
                stats = getattr(processor, "last_fill_stats", None)
                if isinstance(stats, dict):
                    miss_n = int(stats.get("missing_count", 0))
                    if miss_n > 0:
                        miss_list = ", ".join([str(x) for x in stats.get("missing", [])])
                        print(f"记录 {i}: 未找到关键词 {miss_n} 项 -> {miss_list}")
            except Exception:
                pass

        print("批量填充完成，共生成 {} 个文件：".format(len(outputs)))
        for p in outputs:
            print(f" - {p}")
        return

    # 单次模式
    data_pairs = build_data_from_args(args)
    if not data_pairs:
        # 默认示例数据，便于一键体验
        data_pairs = {"身份证号：": "123456789012345678", "企业名称：": "某某科技有限公司"}
        logger.info("未提供数据，使用默认示例：%s", data_pairs)

    # 加载关键词配置（偏移等覆盖）
    kw_overrides = load_keywords_config(kw_config_path)

    # 执行填充
    processor = PDFProcessor()
    # 若未显式提供 --output，但传入了 --output-prefix，则按前缀生成带时间戳的输出路径
    if args.output is None and args.output_prefix:
        args.output = FileHandler.timestamped_output_path(
            input_pdf,
            suffix=CONST_DEFAULT_OUTPUT_SUFFIX,
            prefix=args.output_prefix,
        )
    out = processor.fill_by_keywords(
        input_pdf,
        data_pairs,
        per_key_overrides=kw_overrides,
        output_path=args.output,
        pages=args.pages,
        fuzzy_threshold=getattr(args, "fuzzy_threshold", None),
        engine=args.engine,
    )
    print(f"填充完成，保存至：{out}")
    # 展示未命中统计
    try:
        stats = getattr(processor, "last_fill_stats", None)
        if isinstance(stats, dict):
            miss_n = int(stats.get("missing_count", 0))
            if miss_n > 0:
                miss_list = ", ".join([str(x) for x in stats.get("missing", [])])
                print(f"未找到关键词：{miss_n} 项 -> {miss_list}")
            else:
                print("未找到关键词：0")
    except Exception:
        pass


if __name__ == "__main__":
    main()


