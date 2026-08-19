"""通用断言：减少测试里重复样板代码。"""
from __future__ import annotations

import re
import time
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
        message = str(payload.get("message", ""))
        assert expected_msg_contains in message, (
            f"message 未包含 '{expected_msg_contains}', 实际 '{message}'"
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
_TOKEN_RE = re.compile(r"""
    \[
        (?:
            (\d+)              # 数字下标
            |
            '([^']+)'          # 字符串 key
            |
            "([^"]+)"          # 字符串 key 双引号
        )
    \]
""", re.VERBOSE)


def _resolve_path(data: Any, path: str) -> Any:
    """按 'a.b[0].c' 这样的路径取值。支持点号 + 方括号（数字/字符串）。"""
    cur = data
    # 把 a[0].b[1] 拆成 tokens
    for part in path.split("."):
        # 处理 part 内部的 [..]
        idx = 0
        while idx < len(part):
            m = _TOKEN_RE.match(part, idx)
            if m:
                key = m.group(1) or m.group(2) or m.group(3)
                if m.group(1) is not None:  # 数字下标
                    cur = cur[int(key)]
                else:
                    cur = cur[key]
                idx = m.end()
            else:
                # 普通字段名
                key = part[idx:]
                if key != "":
                    cur = cur[key]
                break
    return cur


def assert_json_path(response: Response, path: str, expected: Any) -> dict[str, Any]:
    """断言响应体里某路径的值 == expected。

    用法:
        assert_json_path(resp, "data.orders[0].order_id", "O1")
    """
    payload = response.json()
    try:
        actual = _resolve_path(payload, path)
    except (KeyError, IndexError, TypeError) as e:
        raise AssertionError(
            f"路径 '{path}' 解析失败: {e}\n响应: {payload}"
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
