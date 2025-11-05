"""
文件路径：src/data_handler.py

模块职责：
- 解析用户输入的数据（键为关键词、值为填充值），并进行基础清洗（去除空值）。
- 加载关键词配置（如默认页面、偏移量覆盖），与用户输入数据配合使用。

说明：
- 仅依赖标准库与 `src/variables.py`，不直接依赖业务模块。

变量引用说明（来自 src/variables.py）：
- PATH_KEYWORDS_JSON, CONST_ENCODING, ERR_CONFIG_LOAD_FAILED

组件调用说明（供业务模块）：
- load_keywords_config：读取关键词覆盖配置（页码与偏移）
- sanitize_input_data：过滤空值，保证填充数据有效
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping, Optional, List, Tuple

from .components import get_logger, split_aliases
from .variables import (
    PATH_KEYWORDS_JSON,
    PATH_TEMPLATES_JSON,
    CONST_ENCODING,
    ERR_CONFIG_LOAD_FAILED,
)


logger = get_logger(__name__)


def _json_loads_strip_bom(content: str):
    """解析 JSON 字符串，自动去除 UTF-8 BOM。"""
    if content.startswith("\ufeff"):
        content = content.lstrip("\ufeff")
    return json.loads(content)


def load_keywords_config(config_path: Optional[Path] = None) -> Dict[str, dict]:
    """加载关键词配置 JSON。

    参数：
        config_path: 配置路径；默认读取 `config/keywords.json`。

    返回：
        以关键词为键的配置字典，例如：{"身份证号：": {"page": 0, "offset_x": 50}}。
    """
    path = config_path or PATH_KEYWORDS_JSON
    if not path.exists():
        logger.warning("找不到关键词配置文件，将使用空配置：%s", path)
        return {}
    try:
        content = path.read_text(encoding=CONST_ENCODING)
        data = _json_loads_strip_bom(content)
        # 仅保留第一层为 dict 的项
        raw_items = {str(k): (v if isinstance(v, dict) else {}) for k, v in data.items() if k != "示例配置说明"}

        # 规范化：支持别名语法（竖线分隔）。
        # - 以第一段作为“规范名（canonical）”作为键返回；
        # - 在配置中附加 "aliases": [ ... ]（含所有别名，含规范名），供业务端查找。
        result: Dict[str, dict] = {}
        for raw_key, cfg in raw_items.items():
            aliases = split_aliases(raw_key)
            canonical = aliases[0] if aliases else str(raw_key).strip()
            merged = dict(cfg)
            # 去重并确保规范名也在 aliases 中
            alias_set = []
            seen: set[str] = set()
            for a in aliases:
                if a not in seen:
                    seen.add(a)
                    alias_set.append(a)
            if canonical not in seen:
                alias_set.insert(0, canonical)
            merged["aliases"] = alias_set
            result[canonical] = merged
        return result
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"[{ERR_CONFIG_LOAD_FAILED}] 配置加载失败: {exc}") from exc


def sanitize_input_data(raw: Mapping[str, Optional[str]]) -> Dict[str, str]:
    """过滤空值（None、空字符串、仅空白），返回新字典。

    参数：
        raw: 原始输入映射（关键词 -> 文本）。

    返回：
        仅包含有效值的字典。
    """
    cleaned: Dict[str, str] = {}
    for k, v in raw.items():
        if v is None:
            continue
        vs = str(v).strip()
        if vs == "":
            continue
        cleaned[str(k)] = vs
    return cleaned


def load_batch_json(path: Path) -> List[Dict[str, str]]:
    """从 JSON 文件加载批量记录。

    支持两种结构：
    - 数组：[{"身份证号：": "...", "企业名称：": "..."}, {...}]
    - 对象：{"records": [ ... ]}

    参数：
        path: JSON 文件路径。

    返回：
        记录列表（每条记录为关键词->值的字典，已做空值过滤）。
    """
    content = path.read_text(encoding=CONST_ENCODING)
    data = _json_loads_strip_bom(content)
    if isinstance(data, dict) and "records" in data and isinstance(data["records"], list):
        items = data["records"]
    elif isinstance(data, list):
        items = data
    else:
        raise RuntimeError(f"[{ERR_CONFIG_LOAD_FAILED}] 批量 JSON 结构需为数组或包含 records 数组的对象")

    results: List[Dict[str, str]] = []
    for obj in items:
        if not isinstance(obj, dict):
            continue
        results.append(sanitize_input_data({str(k): (None if obj[k] is None else str(obj[k])) for k in obj}))
    return results


def load_batch_csv(path: Path) -> List[Dict[str, str]]:
    """从 CSV 文件加载批量记录（首行作为表头，表头应为关键词文本）。

    参数：
        path: CSV 文件路径。

    返回：
        记录列表（每条记录为关键词->值的字典，已做空值过滤）。
    """
    import csv

    results: List[Dict[str, str]] = []
    with path.open("r", encoding=CONST_ENCODING, newline="") as f:  # noqa: P103
        reader = csv.DictReader(f)
        for row in reader:
            if row is None:
                continue
            # DictReader 可能返回 OrderedDict，统一转为普通 dict，并过滤空值
            record = {str(k): (None if row[k] is None else str(row[k])) for k in row.keys()}
            results.append(sanitize_input_data(record))
    return results


__all__ = [
    "load_keywords_config",
    "sanitize_input_data",
    "load_batch_json",
    "load_batch_csv",
    "load_templates_index",
    "infer_template_id_from_filename",
]


def load_templates_index(index_path: Optional[Path] = None) -> Dict[str, str]:
    """加载模板索引，返回 模板ID -> 关键词配置文件路径 的映射。

    参数：
        index_path: 索引文件路径，默认 `config/templates.json`。

    返回：
        形如 {"bank_a": "config/keywords_bank_a.json"} 的映射；
        若文件不存在，返回空映射。
    """
    path = index_path or PATH_TEMPLATES_JSON
    if not path.exists():
        logger.warning("模板索引不存在，将使用默认关键词配置：%s", path)
        return {}
    try:
        content = path.read_text(encoding=CONST_ENCODING)
        data = _json_loads_strip_bom(content)
        if not isinstance(data, dict):
            raise RuntimeError("templates.json 必须是对象结构 {模板ID: 配置路径}")
        # 兼容两种结构：
        # 1) 旧结构：{"bank_b": "config/keywords_bank_b.json"}
        # 2) 新结构：{"bank_b": {"path": "config/keywords_bank_b.json", "match_patterns": ["bank_b", "某模板"]}}
        mapping: Dict[str, str] = {}
        for k, v in data.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, str):
                mapping[k] = v
            elif isinstance(v, dict) and isinstance(v.get("path"), str):
                mapping[k] = str(v.get("path"))
        return mapping
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"[{ERR_CONFIG_LOAD_FAILED}] 模板索引加载失败: {exc}") from exc



def infer_template_id_from_filename(input_pdf: Path, index_path: Optional[Path] = None) -> Optional[str]:
    """基于输入 PDF 文件名自动推断模板 ID（不区分大小写）。

    匹配规则（按优先/特异性排序）：
    - 若 templates.json 使用新结构，优先使用每个模板的 match_patterns 进行子串匹配；
    - 否则回退为启发式匹配：模板ID、本地关键词配置文件名（不含扩展名）、去除前缀 "keywords_" 后的片段；
    - 若有多个候选，选择匹配片段最长者；若仍冲突，按模板ID字典序稳定选择；
    - 返回 None 表示无法确定匹配（此时上层应回退默认配置）。

    参数：
        input_pdf: 输入 PDF 路径。
        index_path: 模板索引路径；默认 `config/templates.json`。

    返回：
        推断出的模板 ID，或 None。
    """
    stem = input_pdf.stem.lower()
    try:
        path = index_path or PATH_TEMPLATES_JSON
        if not path.exists():
            return None
        raw = path.read_text(encoding=CONST_ENCODING)
        data = _json_loads_strip_bom(raw)
        if not isinstance(data, dict):
            return None

        candidates: List[Tuple[str, int]] = []  # (template_id, score)

        def _score_for_pattern(p: str) -> int:
            # 简单以匹配片段长度作为特异性评分
            return len(p)

        for tid, val in data.items():
            if not isinstance(tid, str):
                continue
            patterns: List[str] = []
            if isinstance(val, dict):
                # 新结构：读取 path 与 match_patterns
                vpath = val.get("path")
                if isinstance(vpath, str):
                    p_stem = Path(vpath).stem.lower()
                    patterns.extend([p_stem])
                    if p_stem.startswith("keywords_"):
                        patterns.append(p_stem[len("keywords_"):])
                mps = val.get("match_patterns")
                if isinstance(mps, list):
                    for m in mps:
                        if isinstance(m, str) and m.strip():
                            patterns.append(m.strip().lower())
            elif isinstance(val, str):
                # 旧结构：从路径启发出可匹配片段
                p_stem = Path(val).stem.lower()
                patterns.extend([tid.lower(), p_stem])
                if p_stem.startswith("keywords_"):
                    patterns.append(p_stem[len("keywords_"):])
            else:
                continue

            # 去重并过滤空
            uniq_patterns = sorted(set([p for p in patterns if p]))
            best_local_score = 0
            for p in uniq_patterns:
                if p and p in stem:
                    best_local_score = max(best_local_score, _score_for_pattern(p))
            if best_local_score > 0:
                candidates.append((tid, best_local_score))

        if not candidates:
            return None
        # 选分数最高，分数相同按模板ID字典序稳定选择
        candidates.sort(key=lambda t: (-t[1], t[0]))
        return candidates[0][0]
    except Exception:
        return None

