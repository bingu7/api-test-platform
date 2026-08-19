"""订单接口 PO 测试（real 环境）。

学点：
- 下单/查询/取消的正向链路
- 订单号重复 → 400、amount 非法 → 422
- IDOR：别人看你的订单 → 403（权限测试在 test_security.py 单独覆盖）
"""
from __future__ import annotations

import secrets

import allure
import pytest

from apis import OrderAPI, AuthAPI
from core.base_request import HttpClient
from data.builders import OrderData
from utils.assert_helpers import assert_status, attach_response, assert_detail, assert_paginated_list

pytestmark = [pytest.mark.backend]


@allure.feature("订单接口")
class TestOrderFlow:
    @allure.title("下单 → 201 且 status=pending")
    @pytest.mark.smoke
    def test_create_order(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        od = OrderData().with_order_id(f"ORDT_{secrets.token_hex(4)}").build()
        r = order_api.create(**od)
        attach_response(r)
        assert_status(r, 201)
        payload = r.json()
        assert payload["order_id"] == od["order_id"]
        assert payload["amount"] == od["amount"]
        assert payload["status"] == "pending"

    @allure.title("订单号重复 → 400")
    def test_duplicate_order_id(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        od = OrderData().with_order_id("DUPTEST_001").build()
        order_api.create(**od)
        r = order_api.create(**od)  # 同 order_id 再来一次
        attach_response(r)
        assert_status(r, 400)
        assert_detail(r, "订单号已存在")

    @allure.title("amount ≤ 0 → 422")
    @pytest.mark.parametrize("amount", [0, -1, -99.9])
    def test_invalid_amount(self, api_client: HttpClient, amount):
        order_api = OrderAPI(api_client)
        r = order_api.create(f"AMT_{secrets.token_hex(4)}", amount)
        attach_response(r)
        assert_status(r, 422)

    @allure.title("缺 order_id → 422（Pydantic 必填校验）")
    def test_missing_order_id(self, api_client: HttpClient):
        # 带 admin token 但缺 order_id → 后端 Pydantic 校验 422（必填字段）
        r = api_client.post("/api/orders", auth=True, json={"amount": 10})
        attach_response(r)
        assert_status(r, 422)

    @allure.title("查存在订单 → 200")
    @pytest.mark.smoke
    def test_get_order(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        oid = f"ORDG_{secrets.token_hex(4)}"
        order_api.create(oid, 50.0)
        r = order_api.get(oid)
        attach_response(r)
        assert_status(r, 200)
        assert r.json()["order_id"] == oid

    @allure.title("查不存在订单 → 404")
    def test_get_nonexistent(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        r = order_api.get("NOPE_NOPE")
        attach_response(r)
        assert_status(r, 404)

    @allure.title("列本人订单 → 200 且含刚创建的")
    @pytest.mark.smoke
    def test_list_my_orders_includes_created(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        oid = f"ORDL_{secrets.token_hex(4)}"
        order_api.create(oid, 33.0)
        r = order_api.list()
        attach_response(r)
        assert_status(r, 200)
        ids = {o["order_id"] for o in r.json()}
        assert oid in ids

    @allure.title("取消 pending 订单 → 200 且 status 变 cancelled")
    def test_cancel_pending(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        oid = f"ORDC_{secrets.token_hex(4)}"
        order_api.create(oid, 10.0)
        r = order_api.cancel(oid)
        attach_response(r)
        assert_status(r, 200)
        assert r.json()["status"] == "cancelled"
