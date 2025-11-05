请根据以下项目说明开发一个PDF自动填充工具（方案一：关键词定位+坐标写入），要求生成可直接运行的Python代码，并遵循指定的项目结构和功能优先级：

### 项目核心目标
开发一款用于银行场景的PDF自动填充工具，针对无输入框的纯文本PDF合同，通过识别关键词（如“身份证号：”“企业名称：”）定位坐标，自动填充预填信息，无需转换格式，直接操作原文件。


### 技术栈与依赖
- 编程语言：Python 3.8+
- 核心库：pdfplumber（识别文本及坐标）、reportlab（生成文字图层）、PyPDF2（合并PDF）
- 开发工具：Cursor（需生成带详细注释的可运行代码）


### 项目结构要求
需严格遵循以下目录结构，各文件职责明确：
pdf_filler/
├── src/
│ ├── init.py
│ ├── pdf_processor.py # 核心逻辑：关键词定位、文字写入、PDF 合并
│ ├── data_handler.py # 数据处理：解析用户输入、加载配置
│ └── ui.py # 预留图形界面接口（第一阶段暂不实现）
├── examples/
│ ├── blank_contract.pdf # 空白合同示例（代码中需支持替换）
│ └── filled_contract.pdf # 填充后输出示例
├── config/
│ └── keywords.json # 关键词配置文件（支持自定义）
├── tests/
│ └── test_pdf_filler.py # 基础功能测试
├── requirements.txt # 依赖库列表
├── main.py # 程序入口，调用各模块
└── README.md # 说明文档（无需生成，仅作参考）



### 核心功能要求（第一阶段必须实现）
1. **关键词定位功能**：
   - 实现`find_keyword_coordinates`方法，支持模糊匹配（关键词与PDF文本部分重合时可识别）
   - 支持指定页面查找（默认第一页，预留多页扩展接口）
   - 未找到关键词时给出明确警告，不中断程序

2. **基础填充功能**：
   - 通过reportlab生成文字图层，在关键词右侧50像素（可调整）位置填充信息
   - 合并原PDF与文字图层，保留原格式和排版
   - 自动清理临时图层文件，避免冗余
   - 新增：支持自动换行（按配置的 `max_width` 分行，`line_spacing` 控制行距；未配置则保持单行）

3. **数据处理功能**：
   - 支持解析用户输入的自定义关键词-值对（如{"联系电话：": "13800138000"}）
   - 过滤空值输入，避免无效填充

4. **命令行交互**：
   - 在main.py中实现示例调用，支持用户修改输入PDF路径、填充信息
   - 输出清晰的操作日志（如“填充完成，保存至xxx”）


### 代码细节要求
1. 所有函数需包含类型注解和详细注释（说明参数含义、返回值、处理逻辑）
2. 处理常见异常（如文件不存在、页面索引越界），给出友好错误提示
3. 核心类`PDFProcessor`需封装定位、填充、合并逻辑，确保低耦合
4. 示例代码中需包含可直接运行的测试用例（使用examples目录下的文件）

### 自动换行配置（示例）
在 `config/keywords.json` 为任意关键词增加以下字段开启自动换行：
```json
{
  "身份证号：": { "offset_x": 2, "offset_y": 2, "max_width": 180, "line_spacing": 14 },
  "企业名称：": { "offset_x": 2, "offset_y": 2, "max_width": 220, "line_spacing": 14 }
}
```
- **max_width**: 行宽上限（pt）；超出则按字符逐步回退分行。
- **line_spacing**: 行距（pt）；可省略，默认使用 `STYLE_LINE_SPACING`。


### GUI - Raster 清晰度滑杆
- 在 GUI 左侧“选项”卡选择 `engine=raster` 时可见“清晰度（raster）”滑杆（0.5~4.0，步长 0.1）。
- 仅对 `raster` 引擎生效；`pymupdf` 与 `reportlab` 不受影响。
- 建议：x1.0 体积较小但清晰度一般；x2.0 清晰度明显提升；x3.0+ 文件体积会进一步增大。


### 交付内容
1. 按目录结构生成所有Python文件，确保可直接运行（无需修改核心逻辑）
2. 在requirements.txt中列出所有依赖库及版本
3. 在main.py中添加运行说明注释（如何替换文件路径、修改填充信息）


### CLI 进阶用法（命名增强与批量输出）
- 自定义输出前缀（单次模式）：
```bash
python main.py --input examples/blank_contract.pdf \
  --output-prefix mydoc \
  --kv "身份证号：=1234567890" --kv "企业名称：=某某科技"
# 结果示例：output/mydoc_YYYYMMDD_HHMMSS_filled.pdf
```

- 批量 JSON 并设置序号宽度：
```bash
python main.py --input examples/blank_contract.pdf \
  --batch-json examples/batch.json \
  --output-prefix rpt --index-width 2
# 结果示例：..._01_filled.pdf、..._02_filled.pdf
```

- 批量 CSV 并自定义输出目录：
```bash
python main.py --input examples/blank_contract.pdf \
  --batch-csv examples/batch.csv \
  --output-prefix rptcsv --index-width 2 \
  --batch-output-dir output/csv_out
# 输出目录：output/csv_out/
```

### 模板与配置选择逻辑（含自动匹配）
- 优先级（高→低）：`--keywords-json` > `--template-id` > 自动匹配（按输入 PDF 文件名） > 默认配置 `config/keywords.json`。
- 自动匹配说明：当未显式指定前两项时，程序会读取 `config/templates.json`，基于输入文件名进行模板ID推断：
  - 新结构（推荐）：
```json
{
  "default": { "path": "config/keywords.json", "match_patterns": ["default"] },
  "bank_b": { "path": "config/keywords_bank_b.json", "match_patterns": ["bank_b", "合同B"] }
}
```
  - 旧结构（保持兼容）：
```json
{
  "default": "config/keywords.json",
  "bank_b": "config/keywords_bank_b.json"
}
```
- 示例：当输入文件为 `examples/bank_b_contract.pdf` 时，自动匹配 `template_id=bank_b` 并加载 `config/keywords_bank_b.json`；普通 `blank_contract.pdf` 则回落到默认配置。