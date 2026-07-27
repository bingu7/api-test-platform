"""支付 Mock 场景（直接打 Mock，演示非数据驱动写法）。"""
from __future__ import annotations

import allure
import pytest

from core.base_request import HttpClient
from core.mock_db import MockDB
from utils.assert_helpers import assert_business, assert_status, attach_response


@allure.feature("支付模块")
class TestPaymentMock:
    @allure.story("支付成功")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_payment_success(self, raw_client: HttpClient):
        """支付成功 + 数据库状态校验。"""
        response = raw_client.post("/api/payment/status", auth=False)
        attach_response(response)
        assert_status(response, 200)
        payload = assert_business(response, expected_code=0)
        assert payload["data"]["status"] == "paid"
        assert payload["data"]["order_id"].startswith("ORD_")

    @allure.story("支付成功 + 数据库校验")
    def test_payment_with_db_check(self, raw_client: HttpClient, mock_db: MockDB):
        """支付接口返回 200 不算数——必须校验数据库状态。"""
        order_id = "ORD_DB_00002"  # 种子数据：pending
        assert mock_db.get_order(order_id)["status"] == "pending"

        response = raw_client.post(
            "/api/payment/status",
            auth=False,
            json={"order_id": order_id, "status": "paid"},
        )
        attach_response(response)
        assert_status(response, 200)
        payload = assert_business(response, expected_code=0)
        assert payload["data"]["status"] == "paid"

        # 核心：接口返回 paid → 数据库也必须是 paid
        assert mock_db.get_order(order_id)["status"] == "paid"

    @allure.story("支付超时")
    def test_payment_timeout(self, raw_client: HttpClient):
        response = raw_client.post("/api/payment/timeout", auth=False)
        attach_response(response)
        assert_status(response, 504)
        assert_business(response, expected_msg_contains="请求超时")