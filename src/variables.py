"""
文件路径：src/variables.py

模块职责：
- 统一管理全局跨模块变量，确保模块化、无冲突、可追溯，可复用。
- 变量命名规范：{分类前缀}_{描述性名称}（全大写+下划线）。
  - PATH_：路径相关
  - STYLE_：样式相关
  - STATUS_：状态标识
  - CONST_：通用常量
  - ERR_：错误码

使用说明：
- 业务模块严禁定义新的全局变量，必须从本模块导入所需常量。
- 目录路径均使用 pathlib.Path 对象表示，使用时如需字符串请显式 str() 转换。
"""

from pathlib import Path
from typing import Optional, Tuple


# =============================
# 路径（PATH_）
# =============================
# 项目根目录：定位到当前文件（variables.py）的上两级目录
PATH_ROOT: Path = Path(__file__).resolve().parents[1]

# 各功能目录
PATH_SRC_DIR: Path = PATH_ROOT / "src"
PATH_CONFIG_DIR: Path = PATH_ROOT / "config"
PATH_EXAMPLES_DIR: Path = PATH_ROOT / "examples"
PATH_TESTS_DIR: Path = PATH_ROOT / "tests"
PATH_TEMP_DIR: Path = PATH_ROOT / "temp"
PATH_OUTPUT_DIR: Path = PATH_ROOT / "output"
PATH_LOGS_DIR: Path = PATH_ROOT / "logs"

# 关键文件路径
PATH_KEYWORDS_JSON: Path = PATH_CONFIG_DIR / "keywords.json"  # 关键词配置，支持自定义
PATH_DEFAULT_INPUT_PDF: Path = PATH_EXAMPLES_DIR / "blank_contract.pdf"  # 示例空白PDF
PATH_DEFAULT_OUTPUT_PDF: Path = PATH_EXAMPLES_DIR / "filled_contract.pdf"  # 示例输出PDF
PATH_TEMP_OVERLAY_PDF: Path = PATH_TEMP_DIR / "overlay_layer.pdf"  # 文字图层临时文件
PATH_TEMP_MERGED_PDF: Path = PATH_TEMP_DIR / "merged_preview.pdf"  # 合并预览临时文件
PATH_LOG_FILE: Path = PATH_LOGS_DIR / "app.log"  # 应用运行日志
PATH_PROGRESS_LOG: Path = PATH_ROOT / "progress_log.md"  # 进度记录日志

# 模板与界面配置文件路径
PATH_TEMPLATES_JSON: Path = PATH_CONFIG_DIR / "templates.json"  # 界面字段模板保存位置（可选）

# 字体文件（优先使用可嵌入的 TTF/OTF，避免阅读器方块）
PATH_FONT_FILE: Optional[Path] = PATH_ROOT / "config" / "fonts" / "simhei.ttf"


# =============================
# 样式（STYLE_）
# =============================
STYLE_FONT_NAME: str = "Helvetica"  # 默认英文字体；中文请在业务中注册TTF并覆盖
STYLE_FONT_NAME_CJK_PREFERRED: str = "SimSun"  # 偏好的中文字体显示名（注册后可用于中文显示）
STYLE_FONT_NAME_CJK_FALLBACK: str = "STSong-Light"  # ReportLab 内置可用的 CJK 备用字体名
STYLE_FONT_SIZE_DEFAULT: int = 12  # 默认字体大小（pt）
STYLE_TEXT_COLOR_RGB: Tuple[int, int, int] = (0, 0, 0)  # RGB 颜色，黑色
STYLE_OFFSET_X_DEFAULT: float = 50.0  # 从关键词右侧偏移的默认 X（像素/点）
STYLE_OFFSET_Y_DEFAULT: float = 0.0  # 默认 Y 轴微调（向上为正，向下为负）
STYLE_LINE_SPACING: float = 14.0  # 多行文本的行距（pt）
STYLE_RASTER_TEXT_ALPHA: int = 255  # 光栅化文字不透明度（0-255），255 为不透明

# GUI 样式（颜色与布局尺寸）
STYLE_GUI_PRIMARY_COLOR: str = "#0A3D62"  # 深蓝主色
STYLE_GUI_ACCENT_BLUE: str = "#1E88E5"  # 浅蓝 hover
STYLE_GUI_SUCCESS_GREEN: str = "#4CAF50"
STYLE_GUI_WARN_ORANGE: str = "#FF9800"
STYLE_GUI_MUTED_GRAY: str = "#9E9E9E"
STYLE_GUI_BG: str = "#FFFFFF"
STYLE_GUI_CARD_BG: str = "#F5F7FA"
STYLE_GUI_DIVIDER: str = "#E0E0E0"

STYLE_GUI_FONT_FAMILY: str = "微软雅黑"  # Windows 中文默认
STYLE_GUI_FONT_SIZE_BODY: int = 12
STYLE_GUI_FONT_SIZE_TITLE: int = 14

STYLE_GUI_LEFT_PANEL_WIDTH: int = 300
STYLE_GUI_CENTER_PANEL_WIDTH: int = 900
STYLE_GUI_RIGHT_PANEL_WIDTH: int = 280
STYLE_GUI_WINDOW_MIN_WIDTH: int = 1200
STYLE_GUI_WINDOW_MIN_HEIGHT: int = 700


# =============================
# 状态（STATUS_）
# =============================
STATUS_SUCCESS: str = "SUCCESS"  # 操作成功
STATUS_WARNING: str = "WARNING"  # 存在告警但不中断
STATUS_ERROR: str = "ERROR"  # 操作失败
STATUS_NOT_FOUND: str = "NOT_FOUND"  # 目标未找到（如关键词）
STATUS_SKIPPED: str = "SKIPPED"  # 被跳过（如空值过滤）


# =============================
# 常量（CONST_）
# =============================
CONST_ENCODING: str = "utf-8"  # 文件读写默认编码
CONST_PAGE_INDEX_DEFAULT: int = 0  # 默认第一页（0 基）
CONST_FUZZY_MATCH_THRESHOLD: float = 0.60  # 模糊匹配阈值（0~1），越高越严格
CONST_KEYWORD_SEARCH_MAXHINTS: int = 50  # 单页关键词最大候选数量上限
CONST_CLEAN_TEMP_ON_EXIT: bool = True  # 完成后是否清理临时文件
CONST_MAX_RETRY: int = 2  # 通用重试次数，用于 IO 等可重试操作
CONST_DEFAULT_OUTPUT_SUFFIX: str = "_filled.pdf"  # 默认输出文件名后缀
# 输出命名增强：默认前缀与序号宽度（批量输出时使用）
CONST_OUTPUT_PREFIX_DEFAULT: str = ""  # 默认不强制覆盖，留空表示使用输入文件名 stem
CONST_INDEX_PAD_WIDTH_DEFAULT: int = 3  # 批量输出时的序号零填充位数
# 页选择关键字（CLI/内部统一约定）
CONST_PAGE_SELECTION_ALL: str = "all"  # 选择全部页面
CONST_PAGE_SELECTION_AUTO: str = "auto"  # 自动（保持默认策略或按实现决定）
CONST_RASTER_SCALE: float = 2.0  # 光栅渲染比例，2.0 提升清晰度（2x）；如需更清晰可再增大
# 启动时是否输出运行环境能力（例如 PyMuPDF 版本与 insert_font 可用性）
CONST_LOG_PYMUPDF_CAPABILITIES_ON_STARTUP: bool = True

# 坐标钳制：将绘制坐标限制在页面范围内的默认内边距（pt）
CONST_CLAMP_MARGIN_DEFAULT: float = 2.0
# 是否默认启用贴边保护（包含基线钳制与右侧可见性保护）
CONST_ENABLE_CLAMP_DEFAULT: bool = True

# 关键词别名分隔符（竖线）。
# 说明：当配置或输入中的关键词包含该分隔符时，表示同义别名，如
# "身份证号：|身份证号码|身份号码"，工具将尝试用任一别名进行匹配。
CONST_ALIAS_SEPARATOR: str = "|"

# 批量模式：是否默认启用“逐份按输入文件名自动匹配模板ID”
# 说明：当 CLI 未显式提供 --keywords-json / --template-id 时，
#       若开启该开关，将在批量模式中对每条记录基于其输入PDF文件名分别匹配模板ID；
#       记录可通过保留键覆盖（__template_id/__keywords_json）。
CONST_BATCH_AUTO_TEMPLATE_DEFAULT: bool = False

# GUI 模式：快速 / 专家（默认快速模式，仅展示核心选项，专家模式开放全部配置）
CONST_UI_MODE_QUICK: str = "quick"
CONST_UI_MODE_EXPERT: str = "expert"
CONST_UI_MODE_DEFAULT: str = CONST_UI_MODE_QUICK

# 快速模式常用字段预设（用于一键填充示例数据，提升首次体验）
CONST_UI_QUICK_FIELD_PRESETS: Tuple[Tuple[str, str], ...] = (
    ("身份证号：", "123456789012345678"),
    ("企业名称：", "某某科技发展有限公司"),
    ("联系电话：", "13800138000"),
)

# 常见中文字体候选路径（用于自动探测，按顺序优先）
CONST_CANDIDATE_CJK_FONT_PATHS: Tuple[str, ...] = (
    # Windows 常见字体
    "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
    "C:/Windows/Fonts/simsun.ttc",  # 宋体
    "C:/Windows/Fonts/simhei.ttf",  # 黑体
    # macOS 常见字体
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STSong.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/Library/Fonts/SimSun.ttf",
    # Linux 常见字体
    "/usr/share/fonts/truetype/arphic/ukai.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)

# 日志格式（供 logging.basicConfig 使用）
CONST_LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONST_LOG_DATEFMT: str = "%Y-%m-%d %H:%M:%S"


# =============================
# 错误码（ERR_）
# =============================
# 1xxx：文件/路径相关
ERR_FILE_NOT_FOUND: int = 1001  # 输入文件不存在
ERR_INVALID_PDF: int = 1002  # 非法或损坏的 PDF 文件
ERR_PATH_NOT_WRITABLE: int = 1003  # 目标路径不可写

# 2xxx：识别/定位相关
ERR_KEYWORD_NOT_FOUND: int = 2001  # 未找到关键词
ERR_PAGE_INDEX_OUT_OF_RANGE: int = 2002  # 页面索引越界
ERR_TEXT_LAYER_BUILD_FAILED: int = 2003  # 文字图层生成失败

# 3xxx：合并/写入相关
ERR_PDF_MERGE_FAILED: int = 3001  # PDF 合并失败
ERR_PDF_WRITE_FAILED: int = 3002  # PDF 写入失败

# 4xxx：配置/数据相关
ERR_CONFIG_LOAD_FAILED: int = 4001  # 配置加载失败
ERR_DATA_INVALID: int = 4002  # 输入数据非法


# =============================
# 导出声明
# =============================
__all__ = [
    # PATH_
    "PATH_ROOT",
    "PATH_SRC_DIR",
    "PATH_CONFIG_DIR",
    "PATH_EXAMPLES_DIR",
    "PATH_TESTS_DIR",
    "PATH_TEMP_DIR",
    "PATH_OUTPUT_DIR",
    "PATH_LOGS_DIR",
    "PATH_KEYWORDS_JSON",
    "PATH_DEFAULT_INPUT_PDF",
    "PATH_DEFAULT_OUTPUT_PDF",
    "PATH_TEMP_OVERLAY_PDF",
    "PATH_TEMP_MERGED_PDF",
    "PATH_LOG_FILE",
    "PATH_PROGRESS_LOG",
    "PATH_TEMPLATES_JSON",
    "PATH_FONT_FILE",
    # STYLE_
    "STYLE_FONT_NAME",
    "STYLE_FONT_NAME_CJK_PREFERRED",
    "STYLE_FONT_NAME_CJK_FALLBACK",
    "STYLE_FONT_SIZE_DEFAULT",
    "STYLE_TEXT_COLOR_RGB",
    "STYLE_OFFSET_X_DEFAULT",
    "STYLE_OFFSET_Y_DEFAULT",
    "STYLE_LINE_SPACING",
    "STYLE_RASTER_TEXT_ALPHA",
    "STYLE_GUI_PRIMARY_COLOR",
    "STYLE_GUI_ACCENT_BLUE",
    "STYLE_GUI_SUCCESS_GREEN",
    "STYLE_GUI_WARN_ORANGE",
    "STYLE_GUI_MUTED_GRAY",
    "STYLE_GUI_BG",
    "STYLE_GUI_CARD_BG",
    "STYLE_GUI_DIVIDER",
    "STYLE_GUI_FONT_FAMILY",
    "STYLE_GUI_FONT_SIZE_BODY",
    "STYLE_GUI_FONT_SIZE_TITLE",
    "STYLE_GUI_LEFT_PANEL_WIDTH",
    "STYLE_GUI_CENTER_PANEL_WIDTH",
    "STYLE_GUI_RIGHT_PANEL_WIDTH",
    "STYLE_GUI_WINDOW_MIN_WIDTH",
    "STYLE_GUI_WINDOW_MIN_HEIGHT",
    # STATUS_
    "STATUS_SUCCESS",
    "STATUS_WARNING",
    "STATUS_ERROR",
    "STATUS_NOT_FOUND",
    "STATUS_SKIPPED",
    # CONST_
    "CONST_ENCODING",
    "CONST_PAGE_INDEX_DEFAULT",
    "CONST_FUZZY_MATCH_THRESHOLD",
    "CONST_KEYWORD_SEARCH_MAXHINTS",
    "CONST_CLEAN_TEMP_ON_EXIT",
    "CONST_MAX_RETRY",
    "CONST_DEFAULT_OUTPUT_SUFFIX",
    "CONST_OUTPUT_PREFIX_DEFAULT",
    "CONST_INDEX_PAD_WIDTH_DEFAULT",
    "CONST_PAGE_SELECTION_ALL",
    "CONST_PAGE_SELECTION_AUTO",
    "CONST_RASTER_SCALE",
    "CONST_LOG_PYMUPDF_CAPABILITIES_ON_STARTUP",
    "CONST_CLAMP_MARGIN_DEFAULT",
    "CONST_ENABLE_CLAMP_DEFAULT",
    "CONST_ALIAS_SEPARATOR",
    "CONST_BATCH_AUTO_TEMPLATE_DEFAULT",
    "CONST_UI_MODE_QUICK",
    "CONST_UI_MODE_EXPERT",
    "CONST_UI_MODE_DEFAULT",
    "CONST_UI_QUICK_FIELD_PRESETS",
    "CONST_CANDIDATE_CJK_FONT_PATHS",
    "CONST_LOG_FORMAT",
    "CONST_LOG_DATEFMT",
    # ERR_
    "ERR_FILE_NOT_FOUND",
    "ERR_INVALID_PDF",
    "ERR_PATH_NOT_WRITABLE",
    "ERR_KEYWORD_NOT_FOUND",
    "ERR_PAGE_INDEX_OUT_OF_RANGE",
    "ERR_TEXT_LAYER_BUILD_FAILED",
    "ERR_PDF_MERGE_FAILED",
    "ERR_PDF_WRITE_FAILED",
    "ERR_CONFIG_LOAD_FAILED",
    "ERR_DATA_INVALID",
]


