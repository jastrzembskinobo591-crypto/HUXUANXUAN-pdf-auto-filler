"""
文件路径：src/components/__init__.py

说明：
- 最小重构阶段：将原 `src/components.py` 迁移为包入口，保持对外 API 与行为完全一致；
- 后续将按职责逐步拆分至 `components/{io.py, coords.py, text.py, logging.py, page.py, fonts.py}`；
- 业务模块与测试可继续使用 `from src.components import ...` 导入，无需修改。
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable, Iterable, Optional, Type

from ..variables import (
    PATH_LOGS_DIR,
    PATH_OUTPUT_DIR,
    PATH_TEMP_DIR,
    PATH_CONFIG_DIR,
    PATH_LOG_FILE,
    CONST_DEFAULT_OUTPUT_SUFFIX,
    CONST_OUTPUT_PREFIX_DEFAULT,
    CONST_INDEX_PAD_WIDTH_DEFAULT,
    CONST_LOG_FORMAT,
    CONST_LOG_DATEFMT,
    CONST_MAX_RETRY,
    CONST_CANDIDATE_CJK_FONT_PATHS,
    ERR_PATH_NOT_WRITABLE,
    ERR_FILE_NOT_FOUND,
)

# 聚合导出：拆分后的子模块
from .coords import (
    adjust_coords,
    clamp_coords,
    clamp_baseline,
    right_of_bbox,
    right_of_bbox_baseline,
)
from .page import parse_page_selection
from .text import estimate_text_width, split_text_by_width, split_aliases


# =============================
# 日志工具
# =============================
_LOGGER_CONFIGURED: bool = False


def get_logger(name: str) -> logging.Logger:
    """获取 logger，首次调用时配置文件与控制台双输出。

    参数：
        name: 日志记录器名称（一般使用 __name__）。

    返回：
        logging.Logger 对象。
    """
    global _LOGGER_CONFIGURED
    if not _LOGGER_CONFIGURED:
        # 确保日志目录存在
        PATH_LOGS_DIR.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(PATH_LOG_FILE, encoding="utf-8")
        console_handler = logging.StreamHandler()
        logging.basicConfig(
            level=logging.INFO,
            format=CONST_LOG_FORMAT,
            datefmt=CONST_LOG_DATEFMT,
            handlers=[file_handler, console_handler],
        )
        _LOGGER_CONFIGURED = True
    return logging.getLogger(name)


# =============================
# 文件操作
# =============================
class FileHandler:
    """文件与路径相关的通用处理器。"""

    @staticmethod
    def ensure_project_dirs() -> None:
        """确保项目运行所需目录存在：logs/output/temp。

        若目录不存在则自动创建。
        """
        for d in (PATH_LOGS_DIR, PATH_OUTPUT_DIR, PATH_TEMP_DIR):
            d.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_readable_file(path: Path) -> None:
        """校验文件可读。

        参数：
            path: 文件路径。
        异常：
            FileNotFoundError: 文件不存在或不可读。
        """
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"[{ERR_FILE_NOT_FOUND}] 文件不存在或不可读: {path}")

    @staticmethod
    def ensure_parent_writable(target: Path) -> None:
        """确保目标文件的父目录可写，不存在则创建。

        参数：
            target: 目标文件路径。
        异常：
            PermissionError: 目录不可写。
        """
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        # Windows 上 os.access 可能不可靠，尝试创建临时文件验证
        probe = parent / f".__writable_probe_{int(time.time()*1000)}"
        try:
            with open(probe, "w", encoding="utf-8") as f:  # noqa: P103
                f.write("probe")
        except Exception as exc:  # noqa: BLE001
            raise PermissionError(f"[{ERR_PATH_NOT_WRITABLE}] 目录不可写: {parent}") from exc
        else:
            try:
                probe.unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def timestamped_output_path(
        input_pdf: Optional[Path],
        suffix: str = CONST_DEFAULT_OUTPUT_SUFFIX,
        prefix: Optional[str] = None,
    ) -> Path:
        """生成带时间戳的输出路径，位于 output 目录。

        参数：
            input_pdf: 源 PDF 路径；若为 None，则使用默认前缀。
            suffix: 输出文件名后缀（默认 "_filled.pdf"）。
            prefix: 自定义文件名前缀；若提供则覆盖 input_pdf 的 stem。

        返回：
            输出路径，例如 output/contract_20240101_120000_filled.pdf
        """
        FileHandler.ensure_project_dirs()
        ts = time.strftime("%Y%m%d_%H%M%S")
        use_prefix = (prefix if prefix is not None else CONST_OUTPUT_PREFIX_DEFAULT).strip()
        if use_prefix:
            stem = use_prefix
        else:
            stem = input_pdf.stem if input_pdf is not None else "output"
        return PATH_OUTPUT_DIR / f"{stem}_{ts}{suffix}"

    @staticmethod
    def indexed_output_path(
        input_pdf: Optional[Path],
        index: int,
        suffix: str = CONST_DEFAULT_OUTPUT_SUFFIX,
        pad: int = CONST_INDEX_PAD_WIDTH_DEFAULT,
        prefix: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """生成带时间戳与序号的输出路径，便于批量输出。

        参数：
            input_pdf: 源 PDF 路径；None 则使用默认前缀。
            index: 序号（从 1 开始更友好）。
            suffix: 输出文件名后缀（默认 "_filled.pdf"）。
            pad: 序号左侧零填充位数，默认使用全局配置。
            prefix: 自定义文件名前缀；若提供则覆盖 input_pdf 的 stem。
            output_dir: 自定义输出目录；None 则使用默认 PATH_OUTPUT_DIR。

        返回：
            输出路径，例如 output/contract_20240101_120000_001_filled.pdf

        示例：
            >>> FileHandler.indexed_output_path(Path("test.pdf"), 1, prefix="rpt", pad=2)
            Path("output/rpt_20240101_120000_01_filled.pdf")
        """
        target_dir = output_dir if output_dir is not None else PATH_OUTPUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        
        ts = time.strftime("%Y%m%d_%H%M%S")
        use_prefix = (prefix if prefix is not None else CONST_OUTPUT_PREFIX_DEFAULT).strip()
        if use_prefix:
            stem = use_prefix
        else:
            stem = input_pdf.stem if input_pdf is not None else "output"
        idx = str(max(0, int(index))).zfill(int(pad))
        return target_dir / f"{stem}_{ts}_{idx}{suffix}"


# =============================
# 重试机制与错误处理
# =============================
def retry_on_exception(
    retries: int = CONST_MAX_RETRY,
    exceptions: Iterable[Type[BaseException]] = (Exception,),
    delay_s: float = 0.2,
    backoff: float = 2.0,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """装饰器：异常自动重试，含指数退避。

    参数：
        retries: 重试次数（不含首次）。
        exceptions: 触发重试的异常类型集合。
        delay_s: 初始等待秒数。
        backoff: 每次重试的等待倍数。

    返回：
        包装后的可调用对象。
    """

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        def wrapper(*args, **kwargs):
            wait = delay_s
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # type: ignore[misc]
                    if attempt >= retries:
                        raise
                    logger = get_logger(func.__module__)
                    logger.warning("操作失败，准备重试（第 %s 次）：%s", attempt + 1, exc)
                    time.sleep(wait)
                    wait *= backoff
                    attempt += 1

        return wrapper

    return decorator


class ErrorHandler:
    """错误处理相关工具。"""

    @staticmethod
    def format_error(err_code: int, message: str) -> str:
        """生成统一错误信息字符串。"""
        return f"[{err_code}] {message}"


# =============================
# 字体探测与度量（仅使用标准库，供启动诊断与 GUI 提示）
# =============================
def probe_available_cjk_fonts() -> List[Path]:
    """探测可用的 CJK 字体文件（TTF/OTF），按优先级返回去重列表。

    优先级：
    1) 显式指定的 `PATH_FONT_FILE`（若是 .ttf/.otf 且存在）
    2) `config/fonts/` 目录下的 .ttf/.otf 文件（按文件名排序）
    3) `CONST_CANDIDATE_CJK_FONT_PATHS` 列表中存在的 .ttf/.otf 文件

    返回：
        `Path` 列表，按优先级与发现顺序排列，已去重。
    """
    from ..variables import PATH_FONT_FILE  # 延迟导入避免循环

    seen: set[str] = set()
    results: List[Path] = []

    def _add(p: Path) -> None:
        key = str(p.resolve())
        if key not in seen and p.exists() and p.suffix.lower() in {".ttf", ".otf"}:
            seen.add(key)
            results.append(p)

    # 1) 显式指定
    if PATH_FONT_FILE:
        _add(Path(PATH_FONT_FILE))

    # 2) config/fonts 目录
    fonts_dir = PATH_CONFIG_DIR / "fonts"
    if fonts_dir.exists():
        for p in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
            _add(p)

    # 3) 预置候选
    for s in CONST_CANDIDATE_CJK_FONT_PATHS:
        _add(Path(s))

    return results


def pick_preferred_cjk_font() -> Optional[Path]:
    """选择首个可用的 CJK 字体文件，若无可用则返回 None。"""
    fonts = probe_available_cjk_fonts()
    return fonts[0] if fonts else None


# =============================
# 导出声明
# =============================
__all__ = [
    # 日志工具
    "get_logger",
    # 文件操作
    "FileHandler",
    # 坐标处理
    "adjust_coords",
    "clamp_coords",
    "clamp_baseline",
    "right_of_bbox",
    "right_of_bbox_baseline",
    # 重试与错误处理
    "retry_on_exception",
    "ErrorHandler",
    # 页选择解析
    "parse_page_selection",
    # 文本宽度估算
    "estimate_text_width",
    "split_text_by_width",
    # 关键词别名
    "split_aliases",
    # 字体探测
    "probe_available_cjk_fonts",
    "pick_preferred_cjk_font",
]


