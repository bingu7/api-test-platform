"""接口依赖 / 业务链路测试。（Mock 专属）

面试必问：「接口之间怎么串联？」
回答：「用 pytest fixture 链 + 共享 session，模拟真实用户路径——
        登录→查用户信息→创建订单→查订单列表确认入库→支付→校验支付后状态变更。」

设计：
- 全链路用同一个 api_client（session 级 Token 复用）
- 每一步做完后验证 DB 状态，不只是 HTTP 200
- 链路失败时逐行报错，不遮蔽根因

关于测试顺序与状态共享（面试易踩坑点）：
- pytest 不保证类内方法按定义顺序执行（Pytest 默认虽按定义序，但搭配
  --random 或 pytest-xdist 多 worker 时会被打乱）。
- 因此「上一步产物传给下一步」应在 fixture 中显式注入，
  不要用类变量 / 全局变量隐式传递——本链路里 order_id 是硬编码常量，
  所以最简单稳妥的做法就是直接写字面量，避免引入「伪依赖」让人误以为存在强保证。
"""
from __future__ import annotations

import allure
import pytest

pytestmark = pytest.mark.mock_only

from core.base_request import HttpClient
from core.mock_db import MockDB
from utils.assert_helpers import assert_business, assert_status, attach_response


@allure.feature("业务流程")
@allure.story("完整下单支付链路")
@allure.epic("接口依赖联调")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.smoke
class TestWorkflow:
    """登录 → 用户信息 → 下单 → 查单 → 支付 → 状态校验"""

    # 链路用的 order_id 作为类常量，三处步骤共用同一个字面量。
    # ❌ 不要写成 self.ORDER_ID = ... 这种「类变量传状态」——
    #    一旦测试顺序被打乱（--random / xdist），后续步骤拿到的就是 None/脏值。
    ORDER_ID = "WF_TEST_001"

    def test_step1_login(self, raw_client: HttpClient):
        """Step1: 登录获取 Token（raw_client 因为还没 token）。"""
        response = raw_client.post(
            "/api/login",
            auth=False,
            json={"username": "admin", "password": "123456"},
        )
        attach_response(response)
        assert_status(response, 200)
        payload = assert_business(response, expected_code=0, expected_msg_contains="登录成功")
        assert len(payload["access_token"]) >= 32  # 动态 token（F-04 修复后不再固定）
        assert payload["expires_in"] > 0

    def test_step2_user_profile(self, api_client: HttpClient):
        """Step2: 用登录后的 api_client 获取用户信息。"""
        response = api_client.get("/api/user/profile", auth=True)
        attach_response(response)
        assert_status(response, 200)
        payload = assert_business(response, expected_code=0)
        data = payload["data"]
        assert data["username"] == "admin"
        assert data["role"] == "tester"

    def test_step3_create_order(self, api_client: HttpClient, mock_db: MockDB):
        """Step3: 创建订单 → 验证数据库里有这条记录。"""
        response = api_client.post(
            "/api/orders",
            auth=True,
            json={"order_id": self.ORDER_ID, "amount": 299.00},
        )
        attach_response(response)
        assert_status(response, 201)
        payload = assert_business(response, expected_code=0, expected_msg_contains="下单成功")
        assert payload["data"]["order_id"] == self.ORDER_ID
        assert payload["data"]["status"] == "pending"

        # DB 校验
        db_order = mock_db.get_order(self.ORDER_ID)
        assert db_order is not None, "订单未入库"
        assert db_order["amount"] == 299.00
        assert db_order["status"] == "pending"

    def test_step4_orders_list_contains_new_order(self, api_client: HttpClient):
        """Step4: 查订单列表 → 确认刚创建的订单在里面。"""
        response = api_client.get("/api/orders", auth=True)
        attach_response(response)
        assert_status(response, 200)
        payload = assert_business(response, expected_code=0)

        orders = payload["data"]["orders"]
        assert isinstance(orders, list) and len(orders) >= 1

        order_ids = {o["order_id"] for o in orders}
        assert self.ORDER_ID in order_ids, f"新订单未出现在列表中，现有: {order_ids}"

    def test_step5_pay_and_verify(self, api_client: HttpClient, mock_db: MockDB):
        """Step5: 支付 → 接口返回 paid → DB 也 paid。"""
        response = api_client.post(
            "/api/payment/status",
            auth=False,
            json={"order_id": self.ORDER_ID, "status": "paid"},
        )
        attach_response(response)
        assert_status(response, 200)
        payload = assert_business(response, expected_code=0)
        assert payload["data"]["status"] == "paid"

        # 核心：DB 状态必须一致
        db_order = mock_db.get_order(self.ORDER_ID)
        assert db_order is not None
        assert db_order["status"] == "paid", f"DB 状态仍为 {db_order['status']}，应为 paid"