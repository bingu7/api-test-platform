"""数据准备层演示测试（real 环境）。

学习重点——接口测试里「数据」怎么准备、怎么隔离：
1. Builders：构造一组完整、合法的结构体（只写关心的字段）
2. Factories：凑随机值，避免脏数据撞库
3. fixture setup/teardown：测试前后保证 DB 干净
4. 随机性：每次跑用例账号不一样 → 不依赖上次残留

这是真实项目里常被忽略、但对稳定 CI 极关键的细节。
"""
from __future__ import annotations

import secrets

import allure
import pytest

from apis import AuthAPI, OrderAPI, ProductAPI
from core.base_request import HttpClient
from data.builders import UserData, ProductData, OrderData
from data import factories
from utils.assert_helpers import assert_status, attach_response

pytestmark = [pytest.mark.backend]


@allure.feature("数据准备层")
@allure.story("Builder 模式")
class TestBuilders:
    @allure.title("UserData 默认凭证可注册")
    @pytest.mark.smoke
    def test_user_data_default(self, raw_client: HttpClient):
        auth = AuthAPI(raw_client)
        user = UserData().build()
        r = auth.register(user["username"], user["email"], user["password"])
        attach_response(r)
        assert_status(r, 201)

    @allure.title("UserData 链式覆写：短密码测 422")
    def test_user_data_override(self, raw_client: HttpClient):
        # 默认合法；覆写 password 测负向
        user = UserData().with_password("1").build()  # <6
        r = AuthAPI(raw_client).register(user["username"], user["email"], user["password"])
        assert_status(r, 422)

    @allure.title("OrderData 默认 order_id 唯一、不会撞")
    def test_order_data_unique(self, raw_client: HttpClient):
        o1 = OrderData().build()
        o2 = OrderData().build()
        assert o1["order_id"] != o2["order_id"]


@allure.feature("数据准备层")
@allure.story("随机工厂")
class TestFactories:
    @allure.title("fake_username 不撞种子数据")
    @pytest.mark.smoke
    def test_fake_username_collision_free(self):
        for _ in range(20):
            name = factories.fake_username()
            assert name != "admin" and name != "tester"

    @allure.title("fake_amount 产出合法正数")
    def test_fake_amount_positive(self):
        for _ in range(10):
            assert factories.fake_amount() > 0


@allure.feature("数据准备层")
@allure.story("fixture 清理")
class TestFixtureCleanup:
    @allure.title("admin 建商品后清理 → 后续列表不会越积越多")
    @pytest.mark.smoke
    def test_product_createthen_clean(self, api_client: HttpClient, db_helper):
        product_api = ProductAPI(api_client)
        before = db_helper.count_products()
        pid = product_api.create(**ProductData().build()).json()["id"]
        assert db_helper.count_products() == before + 1
        product_api.delete(pid)
        assert db_helper.count_products() == before

    @allure.title("每次跑用例账号不一样（随机凭证）")
    def test_random_credentials_differ(self, raw_client: HttpClient):
        auth = AuthAPI(raw_client)
        creds = {auth.random_credential()["username"] for _ in range(10)}
        # 10 个凭证用户名应都不同
        assert len(creds) == 10
