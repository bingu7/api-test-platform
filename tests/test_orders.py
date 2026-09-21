"""订单 + 异常路径 + 边界用例：数据驱动。（Mock 专属：测 Flask Mock 订单/边界接口）"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_case_response
from utils.excel_reader import filter_cases

pytestmark = pytest.mark.mock_only


def _extra_cases() -> list[dict]:
    """惰性读取订单/异常用例。详见 test_login.py 中对惰性读取的说明。"""
    return filter_cases(
        endpoints={"/api/orders", "/api/not_exist", "/api/orders/NONEXIST_BY_EXCEL",
                   "/api/payment/status", "/api/edge/empty-body"}
    )


def pytest_generate_tests(metafunc):
    """收集期钩子：只对 test_extra_data_driven 注入 argvalues。"""
    if "extra_case" in metafunc.fixturenames:
        metafunc.parametrize(
            "extra_case",
            _extra_cases(),
            ids=lambda c: c["name"],
        )


@allure.feature("订单与异常")
@allure.story("数据驱动")
def test_extra_data_driven(extra_case: dict, api_client: HttpClient):
    allure.dynamic.title(extra_case["name"])

    # 是否带 Token 由 Excel 的 auth 列决定；列缺省时按 Mock 接口设计兜底（订单接口需登录）
    needs_auth = extra_case.get("auth")
    if needs_auth is None:
        needs_auth = extra_case["endpoint"].startswith("/api/orders")
    response = api_client.request(
        extra_case["method"],
        extra_case["endpoint"],
        auth=needs_auth,
        json=extra_case["body"],
    )
    assert_case_response(response, extra_case)