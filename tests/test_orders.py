"""订单 + 异常路径 + 边界用例：数据驱动。"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_case_response
from utils.excel_reader import filter_cases

_EXTRA_CASES = filter_cases(endpoints={"/api/orders", "/api/not_exist", "/api/orders/NONEXIST_BY_EXCEL", "/api/payment/status", "/api/edge/empty-body"})


@allure.feature("订单与异常")
@allure.story("数据驱动")
@pytest.mark.parametrize("case", _EXTRA_CASES, ids=lambda c: c["name"])
def test_extra_data_driven(case: dict, api_client: HttpClient):
    allure.dynamic.title(case["name"])

    # 鉴权判断：登录已在 Excel 覆盖；订单/边界接口按需
    needs_auth = case["endpoint"] in {"/api/orders", "/api/orders/NONEXIST_BY_EXCEL"}
    response = api_client.request(
        case["method"],
        case["endpoint"],
        auth=needs_auth,
        json=case["body"],
    )
    assert_case_response(response, case)