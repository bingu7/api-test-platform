"""订单 + 异常路径：数据驱动。"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_case_response
from utils.excel_reader import filter_cases

_EXTRA_CASES = filter_cases(endpoints={"/api/orders", "/api/not_exist"})


@allure.feature("订单与异常")
@allure.story("数据驱动")
@pytest.mark.parametrize("case", _EXTRA_CASES, ids=lambda c: c["name"])
def test_orders_and_not_found(case: dict, api_client: HttpClient):
    allure.dynamic.title(case["name"])
    # 不存在接口 / 订单列表：有 Token 也可以；鉴权接口会用到 Token
    response = api_client.request(
        case["method"],
        case["endpoint"],
        auth=True,
        json=case["body"],
    )
    payload = assert_case_response(response, case)

    # 订单列表额外做结构断言
    if case["endpoint"] == "/api/orders" and response.status_code == 200:
        orders = payload["data"]["orders"]
        assert isinstance(orders, list) and len(orders) >= 1
        assert {"order_id", "amount", "status"} <= set(orders[0].keys())
