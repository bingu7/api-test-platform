"""通用断言：减少测试里重复样板代码。"""
from __future__ import annotations

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
