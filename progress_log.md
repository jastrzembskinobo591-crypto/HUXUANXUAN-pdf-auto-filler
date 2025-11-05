# 项目进度记录（PDF 自动填充工具）

- 建立时间：初始化
- 说明：记录每次功能开发的关键信息、代码位置与验证结论，便于追溯。

## 当前状态概览（截至 2025-11-05）
### 已完成功能
- 2025-11-04｜最小重构：将 `src/components.py` 包化为 `src/components/`（入口 `__init__.py` 保持原API），新增 `src/processors/` 占位目录（matching/layout/engines）。零业务变更、向后兼容。
- 2025-11-04｜第一次迁移：将坐标/文本/页解析纯函数拆分至 `components/{coords,text,page}.py`，入口聚合导出，零业务变更。
- 2025-11-04｜第二次迁移：将 `_wrap_text_lines` 与三引擎实现拆分至 `processors/{layout.py, engines/*.py}`，`PDFProcessor` 作为门面委托调用，零业务变更。
- 2025-11-04｜第三次迁移：将 `_normalize_text/_best_fuzzy_window/_bbox_of_chars` 拆分至 `processors/matching.py`，保持行为一致。
- 2025-11-04｜回归验证：迁移收口后运行 `python -m pytest -q` → 31 passed，外部 API 不变。
- 2025-11-04｜变量基线审查：逐条核对 `src/variables.py` 中路径/样式/状态/常量/错误码定义，确认命名前缀与用途注释完善，作为后续模块调用的统一来源。
- 2025-11-04｜通用组件重构：完成 `src/components.py` 审查与增强，新增文本宽度估算、自动分割、批量输出自定义目录支持；向后兼容，代码规范检查通过。
- 第一阶段核心链路与增强：关键词模糊定位、自动换行、三引擎填充（PyMuPDF/ReportLab/raster）与自动回退均已闭环。
- 稳定性与兼容：贴边保护、基线钳制、字体探测与运行诊断完善，支持多页与批量处理。
- 模板管理：支持模板索引、文件名自动匹配、批量模式逐份自动匹配及保留键覆盖。
- CLI 扩展：批量 JSON/CSV、输出命名增强、日志能力与启动诊断完善。
- GUI 能力：引擎/清晰度/贴边保护配置、状态区与快捷操作、批量入口、快速/专家模式切换全部实现。
- 2025-11-04｜快速模式深化：在“填充字段配置”区域新增模板引导与“打开模板配置”入口；补充 `config/keywords_bank_b.json` 的自动换行参数；完成贴边保护强验证与恢复；记录 raster 清晰度对比（x1.0≈16KB，x3.0≈42KB）。
- 测试保障：components/data_handler 等模块已加入 pytest 覆盖，批量与模板逻辑具备基础回归用例。
- 2025-11-04｜自动化测试补充：新增 `tests/test_components_wrapping.py`（自动换行/宽度估算）与 `tests/test_components_baseline.py`（基线钳制/贴边保护）；本地运行 `python -m pytest -q` 显示 29 passed。
 - 2025-11-04｜GUI 快速模式验证：一键填充/清空与模板引导入口通过；`pytest tests/test_ui_quick_mode.py -q` → 2 passed；手动验证“打开模板配置”在 `config/templates.json` 不存在时自动创建并成功打开。
 - 2025-11-04｜关键词别名语法：新增 `CONST_ALIAS_SEPARATOR='|'` 与 `split_aliases`；`data_handler.load_keywords_config` 规范化别名为 `aliases`，`pdf_processor.fill_by_keywords` 支持“输入别名 + 配置别名 + 规范名”候选命中，已通过 CLI/GUI 验证。
 - 2025-11-04｜未命中统计显示：`PDFProcessor.last_fill_stats` 汇总 total/matched/missing；CLI 输出“未找到关键词：N 项 -> 列表”，GUI 状态区同步展示“未找到关键词：N”。
- 2025-11-04｜专家参数贯通（fuzzy_threshold）：处理器/CLI/GUI 全链路支持模糊匹配阈值，默认回退全局常量；新增用例 `tests/test_matching_threshold.py` 与 `tests/test_ui_missing_count.py` 验证阈值影响与 GUI 计数。
 - 2025-11-04｜位置微调：`config/keywords.json` 将“身份证号：|身份证号码|身份号码` 的 `offset_x` 调整至 10，避免与冒号重叠，已目视验证。

- 2025-11-05｜页范围参数化测试：新增 `tests/test_page_range_param.py` 覆盖 `pages=all/1/2/1,2/999`；修正测试阈值以避免跨页误匹配（`fuzzy_threshold=0.95`）；本地运行 `python -m pytest -q tests/test_page_range_param.py` → 5 passed。

- 2025-11-05｜别名解析与匹配用例：新增 `tests/test_alias_matching.py` 覆盖“输入别名/规范名/输入含分隔符/未命中”四场景；修正 `PDFProcessor::_resolve_override_for_key` 以将“输入别名集合”与覆盖项 `aliases` 求交集；`pytest -q tests/test_alias_matching.py` → 4 passed。

- 2025-11-05｜GUI 未命中计数扩展：在 `tests/test_ui_missing_count.py` 新增低阈值用例，专家模式 + 阈值 0.50 期望未命中为 0；本地运行 `python -m pytest -q tests/test_ui_missing_count.py` → 2 passed。

### 未完成工作与计划
 - ~~**P0｜页范围参数贯通**：开放“页范围=all/1,3-5”并贯通 CLI/GUI/处理器；补充参数化用例。~~（已在 2025-11-05 完成参数化测试与验证）
 - ~~**P0｜自动化测试补充**：新增“别名解析与匹配”用例（输入/配置别名与优先级）；完善 GUI 未命中计数用例（已新增一条，继续扩展）。~~（已于 2025-11-05 完成别名用例与处理器修正）
 - **P1｜GUI 快速模式深化**：继续打磨常用字段一键填充/清空、基础提示与模板引导文案。
- **P0｜自动化测试补充**：继续为 GUI 状态信息与批量流程新增参数化/集成测试，并在 CI 中接入 pytest；补充模板自动匹配优先级与回退路径用例。
- **P1｜专家模式可用性提升**：为高级选项补充 tooltip 说明与说明文档，提升定位效率。
- **P1｜不可提取文本适配**：识别扫描件/转曲文本场景并给出明确提示；评估 OCR 集成方案（不影响纯文本路径）。
- **P1｜启动诊断扩展**：输出字体度量来源、逐份自动匹配默认值及耗时统计，增强可观测性。
- **P2｜批量体验升级**：GUI 展示批量执行摘要、耗时与导出记录；提供批量进度日志归档与结果汇总。
- **P2｜交付与部署规划**：设计"解压即用"方案（虚拟环境/打包）、整理字体与依赖资源、编写部署说明。

## 历史记录索引
- [2025-11-02 项目记录](docs/progress/2025-11-02.md)：初始化、第一阶段闭环、稳定性修复与 GUI 首版问题排查。
- [2025-11-03 项目记录](docs/progress/2025-11-03.md)：基线对齐、多页与批量能力、自动换行、测试补齐及端到端验证。
- [2025-11-04 项目记录](docs/progress/2025-11-04.md)：GUI 深化（清晰度、贴边保护、批量入口、快捷操作）、启动诊断完善、模式切换与通用组件重构。

## 维护指引
 - 新增阶段记录：在 `docs/progress/` 创建 `{YYYY-MM-DD}.md`；包含“变更内容/变量与组件引用/关键代码/验证步骤/兼容影响/下一步建议”。
 - 同步总览：每完成一项功能，用一句话摘要更新“已完成功能”；将下一步放入“未完成工作与计划”。
 - 执行流程清单：规则审查 → variables → components → 业务实现 → 验证（≤3步/分步骤）→ 文档 → 最小用例 → 出口检查（linter 0 错误）。
 - 模块化与规模：单文件≤400行（UI≤600行），单函数≤80行；必要时先拆分再实现，保持对外 API 不变。

