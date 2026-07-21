"""登录接口：数据驱动 + 裸请求（auth=False）。"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_case_response
from utils.excel_reader import filter_cases

_LOGIN_CASES = filter_cases(endpoints={"/api/login"})


@allure.feature("登录模块")
@allure.story("数据驱动")
@pytest.mark.smoke
@pytest.mark.parametrize("case", _LOGIN_CASES, ids=lambda c: c["name"])
def test_login_data_driven(case: dict, raw_client: HttpClient, mock_server):
    """
    登录场景必须用 raw_client + auth=False。
    若走带 Token 的客户端，负向用例会先成功登录，测的就不是登录接口本身。
    """
    allure.dynamic.title(case["name"])
    allure.attach(
        str(case.get("body")),
        name="请求参数",
        attachment_type=allure.attachment_type.JSON,
    )

    response = raw_client.request(
        case["method"],
        case["endpoint"],
        auth=False,
        json=case["body"],
    )
    assert_case_response(response, case)
