"""通用断言：减少测试里重复样板代码。"""
from __future__ import annotations

import json
import re
from typing import Any

import allure
from requests import Response


def attach_response(response: Response, name: str = "响应") -> None:
    allure.attach(
        f"URL: {response.request.method} {response.request.url}\n"
        f"状态码: {response.status_code}\n"
        f"响应体: {response.text}",
        name=name,
        attachment_type=allure.attachment_type.TEXT,
    )


def assert_status(response: Response, expected: int) -> None:
    assert response.status_code == expected, (
        f"HTTP 状态码不符: 期望 {expected}, 实际 {response.status_code}, body={response.text[:300]}"
    )


def assert_business(
    response: Response,
    *,
    expected_code: int | None = None,
    expected_msg_contains: str | None = None,
) -> dict[str, Any]:
    """解析 JSON 并断言业务 code / message。返回 data 字典。"""
    try:
        payload = response.json()
    except ValueError as e:
        raise AssertionError(f"响应不是 JSON: {response.text[:300]}") from e

    if expected_code is not None:
        assert payload.get("code") == expected_code, (
            f"业务 code 不符: 期望 {expected_code}, 实际 {payload.get('code')}, body={payload}"
        )
    if expected_msg_contains:
        # 两套错误约定并存：Flask Mock 用 {"code","message"}，FastAPI 原生错误用 {"detail"}
        # （422 时 detail 是 list，str() 化后做包含断言即可）
        raw_msg = payload.get("message")
        message = str(raw_msg if raw_msg is not None else payload.get("detail", ""))
        assert expected_msg_contains in message, (
            f"message/detail 未包含 '{expected_msg_contains}', 实际 '{message}'"
        )
    return payload


def assert_case_response(response: Response, case: dict[str, Any]) -> dict[str, Any]:
    """对接 Excel 数据驱动行：status + code + msg。"""
    attach_response(response, name=f"响应-{case.get('name', '')}")
    assert_status(response, case["expected_status"])
    return assert_business(
        response,
        expected_code=case.get("expected_code"),
        expected_msg_contains=case.get("expected_msg"),
    )


def assert_detail(response: Response, expected_contains: str | None = None) -> dict[str, Any]:
    """FastAPI 报错返回 {"detail": "..."}。解析并可选断言 detail 含某关键词。返回 payload。"""
    try:
        payload = response.json()
    except ValueError as e:
        raise AssertionError(f"响应不是 JSON: {response.text[:300]}") from e
    if expected_contains:
        detail = str(payload.get("detail", ""))
        assert expected_contains in detail, (
            f"detail 未包含 '{expected_contains}', 实际 '{detail}'"
        )
    return payload


# ── JSONPath 式断言（轻量实现，不引依赖） ──
# 一次扫描整条路径，把每个 token 独立识别出来。
# 分支顺序有讲究：方括号形式必须排在「字段名」之前——字段名正则已排除 [ ]，
# 所以遇到 '[' 时数字下标/字符串下标会先命中，不会退化成一整段字段名。
#   data.orders[0].order_id  →  field(data) field(orders) index(0) field(order_id)
#   [0]                      →  index(0)
#   a['b.c']                 →  field(a) key('b.c')   ← key 里可以含点号
_PATH_TOKEN_RE = re.compile(r"""
    \[\s*(?P<index>\d+)\s*\]            # [0]        数字下标
  | \[\s*'(?P<skey>[^']*)'\s*\]         # ['key']    单引号字符串 key
  | \[\s*"(?P<dkey>[^"]*)"\s*\]         # ["key"]    双引号字符串 key
  | (?P<field>[^.\[\]]+)                # field      普通字段名
""", re.VERBOSE)


def _tokenize_path(path: str) -> list[tuple[str, Any]]:
    """把路径字符串切成 [('key', 'data'), ('key', 'orders'), ('index', 0), ...]。

    非法路径（如 'a[', 'a..['）会抛 ValueError，而不是被静默跳过——
    静默跳过会让「路径写错」伪装成「字段不存在」，排障时很误导。
    """
    # 容忍 JSONPath 习惯写法：开头的 $ 与紧随其后的点号（$.data.x / $data.x）
    stripped = path.strip()
    if stripped.startswith("$"):
        stripped = stripped[1:].lstrip(".")

    tokens: list[tuple[str, Any]] = []
    pos = 0
    for m in _PATH_TOKEN_RE.finditer(stripped):
        # 两个 token 之间只允许出现「一个点号」（或紧邻，如 orders[0]）。
        # 连续点号 a..b 属于手误，要报错而不是被静默当成 a.b——否则打错路径
        # 会表现为「字段不存在」，误导排障方向。
        gap = "".join(stripped[pos:m.start()].split())
        if gap not in ("", "."):
            raise ValueError(f"路径片段 {gap!r} 无法解析（位置 {pos}）")
        if m.group("index") is not None:
            tokens.append(("index", int(m.group("index"))))
        elif m.group("skey") is not None:
            tokens.append(("key", m.group("skey")))
        elif m.group("dkey") is not None:
            tokens.append(("key", m.group("dkey")))
        else:
            tokens.append(("key", m.group("field")))
        pos = m.end()

    tail = "".join(stripped[pos:].split())
    if tail:
        raise ValueError(f"路径片段 {tail!r} 无法解析（位置 {pos}）")
    if not tokens:
        raise ValueError("路径为空")
    return tokens


def _resolve_path(data: Any, path: str) -> Any:
    """按 'a.b[0].c' 取值。支持点号字段名 + [数字] + ['字符串'] 三种下标，可任意嵌套。

    >>> _resolve_path({'data': {'orders': [{'order_id': 'O1'}]}}, 'data.orders[0].order_id')
    'O1'
    """
    cur = data
    walked = ""
    for kind, token in _tokenize_path(path):
        if kind == "index":
            label = f"[{token}]"
        else:
            label = f".{token}" if walked else str(token)
        try:
            cur = cur[token]
        except KeyError as e:
            raise KeyError(
                f"路径 {path!r} 在 {walked or '<root>'}{label} 处字段不存在: {e}"
            ) from e
        except IndexError as e:
            raise IndexError(
                f"路径 {path!r} 在 {walked or '<root>'}{label} 处下标越界"
                f"（当前长度 {len(cur)}）: {e}"
            ) from e
        except TypeError as e:
            raise TypeError(
                f"路径 {path!r} 在 {walked or '<root>'} 处无法用 {label!r} 取值"
                f"（当前类型 {type(cur).__name__}）: {e}"
            ) from e
        walked += label
    return cur


def assert_json_path(response: Response, path: str, expected: Any) -> dict[str, Any]:
    """断言响应体里某路径的值 == expected，返回完整 payload。

    路径写法（可任意嵌套）：
        "data.orders[0].order_id"      点号 + 数字下标
        "data.orders[0].items[1].name"
        "['a.b']"                      含点号的 key 用引号包起来
        "$.data.orders[0].id"          兼容 JSONPath 的 $ 前缀

    用法:
        assert_json_path(resp, "data.orders[0].order_id", "O1")
    """
    payload = response.json()
    try:
        actual = _resolve_path(payload, path)
    except ValueError as e:
        # 路径本身写错（语法问题）≠ 响应结构不对，分开报错更好定位
        raise AssertionError(
            f"路径 {path!r} 语法非法: {e}\n"
            "支持写法: a.b[0].c  或  a['b.c']  或  $.a.b[0]"
        ) from e
    except (KeyError, IndexError, TypeError) as e:
        raise AssertionError(
            f"路径 {path!r} 解析失败: {e}\n响应: {json.dumps(payload, ensure_ascii=False)[:500]}"
        ) from e
    assert actual == expected, (
        f"路径 '{path}' 值不符: 期望 {expected!r}, 实际 {actual!r}"
    )
    return payload


def assert_response_time(response: Response, max_ms: float) -> float:
    """断言响应时间不超过 max_ms 毫秒。返回实际毫秒数。"""
    elapsed_ms = response.elapsed.total_seconds() * 1000
    assert elapsed_ms <= max_ms, (
        f"响应时间 {elapsed_ms:.1f}ms 超过阈值 {max_ms}ms"
    )
    return elapsed_ms


def assert_paginated_list(response: Response, min_items: int = 1) -> list:
    """断言响应是列表且至少 N 项。返回列表。"""
    payload = response.json()
    assert isinstance(payload, list), f"期望列表，实际 {type(payload).__name__}"
    assert len(payload) >= min_items, f"期望至少 {min_items} 项，实际 {len(payload)}"
    return payload
