"""JSON Schema 结构校验测试。

面试场景：
  「你只断言了 payload["code"] == 0，但如果后端把 amount 从数字改成了字符串 "99.99"，能发现吗？」
  「能——我加了 JSON Schema 校验，类型、枚举、required 字段全覆盖。」
"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_status
from utils.schema_validator import (
    SCHEMA_ERROR,
    SCHEMA_LOGIN_SUCCESS,
    SCHEMA_ORDERS_LIST,
    SCHEMA_USER_PROFILE,
    validate_response,
)


@allure.feature("Schema 校验")
@allure.story("登录响应结构")
@pytest.mark.smoke
def test_login_schema(raw_client: HttpClient):
    """登录成功时响应结构必须符合 SCHEMA_LOGIN_SUCCESS。"""
    response = raw_client.post(
        "/api/login",
        auth=False,
        json={"username": "admin", "password": "123456"},
    )
    assert_status(response, 200)
    payload = validate_response(response, SCHEMA_LOGIN_SUCCESS, "登录成功")
    # 额外断言：Schema 已校验类型，这里只需校验值
    assert len(payload["access_token"]) >= 32  # 动态 token（F-04 修复后不再固定）
    assert payload["expires_in"] > 0


@allure.feature("Schema 校验")
@allure.story("用户信息响应结构")
def test_user_profile_schema(api_client: HttpClient):
    """用户信息响应结构必须符合 SCHEMA_USER_PROFILE（含 data 嵌套）。"""
    response = api_client.get("/api/user/profile", auth=True)
    assert_status(response, 200)
    payload = validate_response(response, SCHEMA_USER_PROFILE, "用户信息")
    assert payload["data"]["username"] == "admin"


@allure.feature("Schema 校验")
@allure.story("订单列表响应结构")
def test_orders_list_schema(api_client: HttpClient):
    """订单列表每条 item 必须符合 SCHEMA_ORDER（amount>0, status枚举）。"""
    response = api_client.get("/api/orders", auth=True)
    assert_status(response, 200)
    validate_response(response, SCHEMA_ORDERS_LIST, "订单列表")


@allure.feature("Schema 校验")
@allure.story("错误响应结构")
@allure.severity(allure.severity_level.NORMAL)
def test_error_response_schema(raw_client: HttpClient):
    """所有错误响应（登录失败等）必须符合 SCHEMA_ERROR。"""
    response = raw_client.post(
        "/api/login",
        auth=False,
        json={"username": "admin", "password": "wrong"},
    )
    assert_status(response, 401)
    validate_response(response, SCHEMA_ERROR, "错误响应")