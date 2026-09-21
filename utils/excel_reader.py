"""
Excel 数据驱动读取。

约定列：
- case_name (必填)
- endpoint (必填)
- method (必填)
- body (可选 JSON 字符串)
- expected_status (必填)
- expected_code (可选)
- expected_msg (可选)
- auth (可选：1/0/true/false，表示该用例是否需要带 Token；缺省 None，由测试侧按接口设计兜底)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from utils.paths import data_file

REQUIRED_COLUMNS = (
    "case_name",
    "endpoint",
    "method",
    "expected_status",
)


def _cell_str(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return None
    return text


def _parse_bool(raw: Any) -> bool | None:
    """解析 Excel 里的布尔单元格：1/true/yes → True；0/false/no → False；空 → None。"""
    text = _cell_str(raw)
    if text is None:
        return None
    if text.lower() in ("1", "true", "yes", "是"):
        return True
    if text.lower() in ("0", "false", "no", "否"):
        return False
    raise ValueError(f"auth 列不是合法布尔值: {text!r}")


def _parse_body(raw: Any) -> dict | list | None:
    text = _cell_str(raw)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"body 不是合法 JSON: {text!r}") from e


def read_test_cases(file_path: str | Path | None = None) -> list[dict[str, Any]]:
    """
    读取 Excel 用例。
    默认读取 data/test_cases.xlsx（基于项目根绝对路径）。
    """
    path = Path(file_path) if file_path else data_file("test_cases.xlsx")
    if not path.is_absolute():
        # 相对路径一律相对项目 data 或 cwd 的显式路径；优先当文件名
        candidate = data_file(path.name) if path.parent == Path(".") else path
        path = candidate if candidate.exists() else Path(file_path)  # type: ignore[arg-type]

    if not path.exists():
        raise FileNotFoundError(f"测试数据文件不存在: {path.resolve()}")

    df = pd.read_excel(path, dtype=str)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Excel 缺少必要列 {missing}，当前列: {list(df.columns)}")

    cases: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        name = _cell_str(row.get("case_name"))
        endpoint = _cell_str(row.get("endpoint"))
        method = _cell_str(row.get("method"))
        status_raw = _cell_str(row.get("expected_status"))

        if not name or not endpoint or not method or not status_raw:
            raise ValueError(f"第 {int(idx) + 2} 行缺少必填字段 (name/endpoint/method/status)")

        code_raw = _cell_str(row.get("expected_code"))
        try:
            expected_status = int(status_raw)
        except ValueError as e:
            raise ValueError(
                f"第 {int(idx) + 2} 行 expected_status 不是合法数字: {status_raw!r}"
            ) from e
        try:
            expected_code = int(code_raw) if code_raw is not None else None
        except ValueError as e:
            raise ValueError(
                f"第 {int(idx) + 2} 行 expected_code 不是合法数字: {code_raw!r}"
            ) from e
        cases.append(
            {
                "name": name,
                "endpoint": endpoint,
                "method": method.upper(),
                "body": _parse_body(row.get("body")),
                "expected_status": expected_status,
                "expected_code": expected_code,
                "expected_msg": _cell_str(row.get("expected_msg")),
                "auth": _parse_bool(row.get("auth")),
            }
        )
    return cases


def filter_cases(
    cases: list[dict[str, Any]] | None = None,
    *,
    endpoints: set[str] | None = None,
    file_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """按 endpoint 过滤用例。endpoints 必须是 set[str] 而非单个字符串。"""
    if endpoints is not None and not isinstance(endpoints, set):
        raise TypeError(
            f"filter_cases 的 endpoints 参数必须为 set，收到 {type(endpoints).__name__}: {endpoints!r}\n"
            "例如: filter_cases(endpoints={'/api/login'}) — 注意是大括号不是不带括号的字符串"
        )
    data = cases if cases is not None else read_test_cases(file_path)
    if endpoints is None:
        return data
    return [c for c in data if c["endpoint"] in endpoints]
