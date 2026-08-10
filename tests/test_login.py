"""登录接口：数据驱动 + 裸请求（auth=False）。"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_case_response
from utils.excel_reader import filter_cases


def _login_cases() -> list[dict]:
    """惰性读取登录用例。

    ❌ 反模式（曾经写法）：模块顶层写 `_LOGIN_CASES = filter_cases(...)`
       —— 这会让 import 该测试模块时就触发 Excel I/O，
       `pytest --collect-only` / `--co` 拿来收集时也真的读盘，
       一旦 Excel 文件缺失/损坏，错误是 Collection Error 而不是测试失败。
    ✅ 正模式：用 pytest_generate_tests 钩子把读取推迟到「该模块被实际收集」时，
       并通过 fixture 注入到测试，做到「不收集则不读」。
    """
    return filter_cases(endpoints={"/api/login"})


def pytest_generate_tests(metafunc):
    """收集期钩子：只对 test_login_data_driven 注入 argvalues。"""
    if "login_case" in metafunc.fixturenames:
        metafunc.parametrize(
            "login_case",
            _login_cases(),
            ids=lambda c: c["name"],
        )


@allure.feature("登录模块")
@allure.story("数据驱动")
@pytest.mark.smoke
def test_login_data_driven(login_case: dict, raw_client: HttpClient, mock_server):
    """
    登录场景必须用 raw_client + auth=False。
    若走带 Token 的客户端，负向用例会先成功登录，测的就不是登录接口本身。
    """
    case = login_case
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
