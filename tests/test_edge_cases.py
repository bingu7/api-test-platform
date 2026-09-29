"""边界 + 异常用例测试。（Mock 专属：覆盖 Flask Mock 的边界接口）"""

from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_business, assert_status, attach_response

pytestmark = pytest.mark.mock_only


@allure.feature("边界测试")
class TestEdgeCases:
    """非 Excel 数据驱动的边界用例（代码演示）。"""

    @allure.story("未登录鉴权")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_unauthorized_access(self, raw_client: HttpClient):
        """无Token访问鉴权接口必须401。"""
        endpoints = ["/api/user/profile", "/api/orders"]
        for ep in endpoints:
            response = raw_client.get(ep, auth=False)
            assert_status(response, 401)
            assert_business(response, expected_msg_contains="未授权")

    @allure.story("空请求体")
    def test_empty_body(self, raw_client: HttpClient):
        response = raw_client.post(
            "/api/edge/empty-body",
            auth=False,
            headers={"Content-Type": "application/json"},
            data="",
        )
        assert_status(response, 422)
        assert_business(response, expected_msg_contains="请求体不能为空")

    @allure.story("非JSON Content-Type")
    def test_wrong_content_type(self, raw_client: HttpClient):
        response = raw_client.post(
            "/api/edge/empty-body",
            auth=False,
            headers={"Content-Type": "text/plain"},
            data="not-json-data",
        )
        assert_status(response, 400)
        assert_business(response, expected_msg_contains="Content-Type")

    @allure.story("必填字段缺失")
    def test_missing_required_field(self, raw_client: HttpClient):
        response = raw_client.post(
            "/api/edge/missing-field",
            auth=False,
            json={"extra": "not-what-we-need"},
        )
        assert_status(response, 422)
        assert_business(response, expected_msg_contains="缺少必填字段")

    @allure.story("超大Payload")
    def test_large_payload(self, raw_client: HttpClient):
        response = raw_client.post(
            "/api/edge/large-payload",
            auth=False,
            json={"text": "x" * 15000},
        )
        assert_status(response, 413)
        assert_business(response, expected_msg_contains="请求体过大")

    @allure.story("服务端异常")
    @allure.severity(allure.severity_level.MINOR)
    def test_server_error(self, raw_client: HttpClient):
        response = raw_client.get("/api/edge/fatal-error", auth=False)
        assert_status(response, 500)

    @allure.story("查询不存在的资源")
    def test_nonexistent_order_404(self, api_client: HttpClient):
        """查一个不存在的订单应返回 404 + 明确消息。"""
        response = api_client.get("/api/orders/NONEXISTENT", auth=True)
        assert_status(response, 404)
        assert_business(response, expected_msg_contains="不存在")

    @allure.story("创建订单金额为0")
    def test_create_order_zero_amount(self, api_client: HttpClient):
        """金额 <= 0 应被拒绝。"""
        response = api_client.post(
            "/api/orders",
            auth=True,
            json={"order_id": "ZERO_TEST", "amount": 0},
        )
        assert_status(response, 400)
        assert_business(response, expected_msg_contains="金额必须大于 0")