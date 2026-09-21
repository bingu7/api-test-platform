"""支付接口 PO 测试（real 环境）。

学点：
- 正常支付：订单 pending → paid，payment 记录 success
- 幂等：同 idempotency_key 重复 → 返回首次记录，不重复扣款
- 退款：已支付单 → payment refunded、订单回 pending
- 已支付订单不允许重复支付（换 key）；未支付订单退不了款
"""
from __future__ import annotations

import secrets

import allure
import pytest

from apis import OrderAPI, PaymentAPI
from core.base_request import HttpClient
from utils.assert_helpers import assert_status, assert_detail, attach_response

pytestmark = [pytest.mark.backend]


def _new_order(order_api: OrderAPI) -> str:
    """造一个 pending 订单，返回 order_id。"""
    oid = f"PAYT_{secrets.token_hex(4)}"
    r = order_api.create(oid, 88.0)
    assert r.status_code == 201, r.text
    return oid


@allure.feature("支付接口")
class TestPayment:
    @allure.title("支付 pending 订单 → 200 且 success")
    @pytest.mark.smoke
    def test_pay_success(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = _new_order(order_api)
        key = f"idem_{secrets.token_hex(8)}"
        r = payment_api.pay(oid, idempotency_key=key)
        attach_response(r)
        assert_status(r, 200)
        payload = r.json()
        assert payload["status"] == "success"
        assert payload["amount"] == 88.0
        assert payload["idempotency_key"] == key
        # 订单状态应已变 paid
        assert order_api.get(oid).json()["status"] == "paid"

    @allure.title("同 idempotency_key 重复支付 → 幂等返回首次记录")
    @pytest.mark.smoke
    def test_idempotent_pay(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = _new_order(order_api)
        key = f"idem_{secrets.token_hex(8)}"
        r1 = payment_api.pay(oid, idempotency_key=key)
        r2 = payment_api.pay(oid, idempotency_key=key)
        attach_response(r1)
        assert_status(r1, 200)
        assert_status(r2, 200)
        # 幂等：两次返回的是同一条记录（id 一致）
        assert r1.json()["id"] == r2.json()["id"]
        # 支付记录只有一条（没重复扣款）
        assert payment_api.status(oid).json()["id"] == r1.json()["id"]

    @allure.title("已支付订单换 key 再付 → 400")
    def test_pay_already_paid(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = _new_order(order_api)
        payment_api.pay(oid, idempotency_key=f"k_{secrets.token_hex(8)}")
        r = payment_api.pay(oid, idempotency_key=f"another_{secrets.token_hex(8)}")
        attach_response(r)
        assert_status(r, 400)
        assert_detail(r, "订单已支付")

    @allure.title("幂等键被其他订单占用 → 400（不回放他人支付记录）")
    def test_idempotency_key_bound_to_order(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid_a = _new_order(order_api)
        oid_b = _new_order(order_api)
        shared_key = f"shared_{secrets.token_hex(8)}"
        r1 = payment_api.pay(oid_a, idempotency_key=shared_key)
        assert_status(r1, 200)
        # 同一用户把同 key 用到另一笔订单 → 冲突，不允许返回订单 A 的支付单
        r2 = payment_api.pay(oid_b, idempotency_key=shared_key)
        attach_response(r2)
        assert_status(r2, 400)
        assert_detail(r2, "幂等键已被其他订单使用")

    @allure.title("退款已支付订单 → 200 且 refunded、订单回 pending")
    def test_refund(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = _new_order(order_api)
        payment_api.pay(oid, idempotency_key=f"k_{secrets.token_hex(8)}")
        r = payment_api.refund(oid)
        attach_response(r)
        assert_status(r, 200)
        assert r.json()["status"] == "refunded"
        # 订单回到 pending（可再次支付/取消）
        assert order_api.get(oid).json()["status"] == "pending"

    @allure.title("未支付订单退款 → 400")
    def test_refund_unpaid(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = _new_order(order_api)
        r = payment_api.refund(oid)
        attach_response(r)
        assert_status(r, 400)
        assert_detail(r, "未支付")

    @allure.title("查不存在的支付记录 → 404")
    def test_status_nonexistent_payment(self, api_client: HttpClient):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = _new_order(order_api)  # 没支付
        r = payment_api.status(oid)
        attach_response(r)
        assert_status(r, 404)
