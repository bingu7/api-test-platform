"""用户模块：鉴权 + 结构断言。（Mock 专属：测 Flask Mock 用户接口）"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_business, assert_status, attach_response

pytestmark = pytest.mark.mock_only


@allure.feature("用户模块")
@allure.story("个人信息")
@allure.title("获取用户信息（需鉴权）")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_user_profile(api_client: HttpClient):
    response = api_client.get("/api/user/profile", auth=True)
    attach_response(response)
    assert_status(response, 200)
    payload = assert_business(response, expected_code=0, expected_msg_contains="获取成功")
    data = payload["data"]
    assert data["username"] == "admin"
    assert data["role"] == "tester"


@allure.feature("用户模块")
@allure.story("鉴权")
@allure.title("无 Token 访问用户信息应 401")
def test_user_profile_unauthorized(raw_client: HttpClient):
    response = raw_client.get("/api/user/profile", auth=False)
    attach_response(response)
    assert_status(response, 401)
    assert_business(response, expected_code=-1, expected_msg_contains="未授权")
