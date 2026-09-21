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
- 并行执行注意：xdist 每个 worker 有独立的 MockServer/MockDB（内存库不跨进程共享），
  链路各步骤若被分到不同 worker，step3 建的单在 step4 的库里不存在。
  故本类打了 @pytest.mark.xdist_group("workflow")，
  并行时请加 --dist loadgroup（同组用例捆绑到同一 worker 且保持顺序）：
      pytest tests/ -n auto --dist loadgroup
"""
from __future__ import annotations

import allure
import pytest

pytestmark = [pytest.mark.mock_only, pytest.mark.xdist_group("workflow")]

from core.base_request import HttpClient
from core.mock_db import MockDB
from utils.assert_helpers import (
    assert_business,
    assert_json_path,
    assert_status,
    attach_response,
)


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

        # 用 JSONPath 式断言扎进嵌套结构——比手动 payload["data"]["orders"] 逐层取
        # 更能表达「断言的是响应结构的哪一处」，路径写错时报错会直接指出断在哪一级。
        # 先确认列表元素结构（下标 0 的元素形态固定，可安全断言字段）
        assert_json_path(response, "data.orders[0].amount", orders[0]["amount"])

        # 再定位到本次新建的那条订单。
        # ⚠️ 不能用固定的 orders[0]：MockDB 用 dict 存储，list_orders() 按插入序返回，
        #    种子单（ORD_DB_00001…）永远排在前面。写死下标会变成「依赖别人没先建单」的
        #    脆弱断言，所以按下标动态拼路径。
        idx = next(i for i, o in enumerate(orders) if o["order_id"] == self.ORDER_ID)
        assert_json_path(response, f"data.orders[{idx}].order_id", self.ORDER_ID)
        assert_json_path(response, f"data.orders[{idx}].status", "pending")

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