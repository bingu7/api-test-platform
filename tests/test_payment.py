"""支付 Mock 场景（直接打 Mock，演示非数据驱动写法）。（Mock 专属）"""
from __future__ import annotations

import secrets

import allure
import pytest

from core.base_request import HttpClient
from core.mock_db import MockDB
from utils.assert_helpers import assert_business, assert_status, attach_response

pytestmark = pytest.mark.mock_only


@allure.feature("支付模块")
class TestPaymentMock:
    @allure.story("支付成功 + 数据库校验")
    @pytest.mark.smoke
    @allure.severity(allure.severity_level.BLOCKER)
    def test_payment_with_db_check(self, api_client: HttpClient, raw_client: HttpClient, mock_db: MockDB):
        """支付接口返回 200 不算数——必须校验数据库状态。

        自己建单、自己支付，不依赖种子单的初始状态——
        否则任何先跑的数据驱动用例动了同一颗种子单，本用例就会假挂。
        """
        order_id = f"PAYMOCK_{secrets.token_hex(4)}"
        create = api_client.post("/api/orders", auth=True,
                                 json={"order_id": order_id, "amount": 66.0})
        assert_status(create, 201)
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