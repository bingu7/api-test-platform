"""后端 Excel 数据驱动用例（real 环境）：读取 data/backend_cases.xlsx。

与 dev 环境 tests/test_login.py 的区别：
- 鉴权不硬编码在 Python 里——由 Excel 的 auth 列决定（1=带 Token，0=不带），
  新增一行用例不需要改任何代码。
- 仍保持「惰性读取」：用 pytest_generate_tests 把 Excel I/O 推迟到收集该模块时，
  pytest --collect-only 全局收集时不会无谓读盘（详见 test_login.py 里的反模式说明）。
"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_case_response
from utils.excel_reader import read_test_cases
from utils.paths import data_file

pytestmark = [pytest.mark.backend]


def _backend_cases() -> list[dict]:
    return read_test_cases(data_file("backend_cases.xlsx"))


def pytest_generate_tests(metafunc):
    """收集期钩子：只对 test_backend_data_driven 注入 argvalues。"""
    if "backend_case" in metafunc.fixturenames:
        metafunc.parametrize(
            "backend_case",
            _backend_cases(),
            ids=lambda c: c["name"],
        )


@allure.feature("后端数据驱动")
@allure.story("Excel 用例")
def test_backend_data_driven(backend_case: dict, api_client: HttpClient):
    allure.dynamic.title(backend_case["name"])
    allure.attach(
        str(backend_case.get("body")),
        name="请求参数",
        attachment_type=allure.attachment_type.JSON,
    )

    # 是否带 Token 由 Excel auth 列决定；缺省时按后端接口设计兜底（订单接口需登录）
    needs_auth = backend_case.get("auth")
    if needs_auth is None:
        needs_auth = backend_case["endpoint"].startswith("/api/orders")
    response = api_client.request(
        backend_case["method"],
        backend_case["endpoint"],
        auth=needs_auth,
        json=backend_case["body"],
    )
    assert_case_response(response, backend_case)
