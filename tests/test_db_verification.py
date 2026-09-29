"""数据库白盒校验测试（real 环境）。

学习重点——「双校验」原则：
- HTTP 200 不代表数据真的落库 / 状态真的变了。
- 接口测试的「地面真相」是直连 DB 检查：API 返回 + DB 实际状态 必须一致。
- 用 utils/db_helper.py 直连 SQLite，绕过后端 ORM 做只读断言。

这些用例用 @pytest.mark.db_check 标记，便于单独跑：
    pytest -m db_check
"""
from __future__ import annotations

import secrets

import allure
import pytest

from apis import AuthAPI, OrderAPI, PaymentAPI
from core.base_request import HttpClient
from data.builders import UserData
from utils.assert_helpers import assert_status, attach_response

pytestmark = [pytest.mark.backend, pytest.mark.db_check]


@allure.feature("DB 落库校验")
@allure.story("注册落库")
class TestDbRegister:
    @allure.title("注册成功后 users 表多一行")
    @pytest.mark.smoke
    def test_register_persisted(self, raw_client: HttpClient, db_helper):
        auth_api = AuthAPI(raw_client)
        before = db_helper.count_users()
        cred = auth_api.random_credential()
        r = auth_api.register(cred["username"], cred["email"], cred["password"])
        attach_response(r)
        assert_status(r, 201)

        # DB 校验：行数 +1，且行里的 username/email/role 与响应一致
        after = db_helper.count_users()
        assert after == before + 1, f"用户未落库: before={before}, after={after}"
        row = db_helper.get_user_by_username(cred["username"])
        assert row is not None
        assert row["email"] == cred["email"]
        assert row["role"] == "user"
        # 安全：DB 里的密码是哈希，不是明文
        assert row["hashed_password"] != cred["password"]
        assert row["hashed_password"].startswith("pbkdf2_sha256$")


@allure.feature("DB 落库校验")
@allure.story("订单落库")
class TestDbOrder:
    @allure.title("下单后 orders 表多一行、状态=pending、归属人正确")
    @pytest.mark.smoke
    def test_order_persisted(self, api_client: HttpClient, db_helper):
        order_api = OrderAPI(api_client)
        # 拿 admin 的 user_id（settings.username=admin）——下单前先记行数
        admin_row = db_helper.get_user_by_username("admin")
        assert admin_row is not None
        before = db_helper.count_orders(user_id=admin_row["id"])

        oid = f"DBO_{secrets.token_hex(4)}"
        r = order_api.create(oid, 123.0)
        attach_response(r)
        assert_status(r, 201)

        row = db_helper.get_order(oid)
        assert row is not None, "订单未入库"
        assert row["amount"] == 123.0
        assert row["status"] == "pending"
        assert row["user_id"] == admin_row["id"]
        after = db_helper.count_orders(user_id=admin_row["id"])
        assert after == before + 1, f"订单数未 +1: before={before}, after={after}"


@allure.feature("DB 落库校验")
@allure.story("支付状态机落库")
class TestDbPayment:
    @allure.title("支付后 payments 表有 success 记录、orders 状态变 paid")
    @pytest.mark.smoke
    def test_payment_state_machine(self, api_client: HttpClient, db_helper):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = f"DBP_{secrets.token_hex(4)}"
        order_api.create(oid, 50.0)

        # 支付前：无支付记录、订单 pending
        assert db_helper.get_latest_payment(oid) is None
        db_helper.assert_order_status(oid, "pending")

        key = f"idem_{secrets.token_hex(8)}"
        r = payment_api.pay(oid, idempotency_key=key)
        attach_response(r)
        assert_status(r, 200)

        # 支付后：payments 表有一条 success、orders 变 paid
        db_helper.assert_payment_status(oid, "success")
        db_helper.assert_order_status(oid, "paid")
        pay = db_helper.get_latest_payment(oid)
        assert pay["idempotency_key"] == key

    @allure.title("退款后 payment 变 refunded、订单回 pending")
    def test_refund_state(self, api_client: HttpClient, db_helper):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = f"DBR_{secrets.token_hex(4)}"
        order_api.create(oid, 20.0)
        payment_api.pay(oid, idempotency_key=f"k_{secrets.token_hex(8)}")
        payment_api.refund(oid)

        db_helper.assert_payment_status(oid, "refunded")
        db_helper.assert_order_status(oid, "pending")


@allure.feature("DB 落库校验")
@allure.story("幂等落库")
class TestDbIdempotency:
    @allure.title("同 key 重复支付，payments 表只多一行")
    def test_idempotent_pays_in_db(self, api_client: HttpClient, db_helper):
        order_api = OrderAPI(api_client)
        payment_api = PaymentAPI(api_client)
        oid = f"DBI_{secrets.token_hex(4)}"
        order_api.create(oid, 7.0)
        key = f"idem_{secrets.token_hex(8)}"

        payment_api.pay(oid, idempotency_key=key)
        before = db_helper.count_payments(oid)
        payment_api.pay(oid, idempotency_key=key)  # 幂等重复

        # payments 表里 oid 的行数没增加
        after = db_helper.count_payments(oid)
        assert after == before == 1, f"幂等失败，支付行数应不变: before={before}, after={after}"
