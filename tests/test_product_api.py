"""商品接口 PO 测试（real 环境）。

学 PO 模式 + 鉴权分层：
- 公开接口（list/get）：auth=False，任何人可看
- 管理接口（create/update/delete）：需 admin token，普通用户 403、无 token 401
"""
from __future__ import annotations

import allure
import pytest

from apis import ProductAPI, AuthAPI
from core.base_request import HttpClient
from data.builders import ProductData
from utils.assert_helpers import assert_status, attach_response, assert_paginated_list

pytestmark = [pytest.mark.backend]


@allure.feature("商品接口")
class TestProductPublic:
    @allure.title("商品列表 → 200 且为非空数组")
    @pytest.mark.smoke
    def test_list_products(self, raw_client: HttpClient):
        product_api = ProductAPI(raw_client)
        r = product_api.list()
        attach_response(r)
        assert_status(r, 200)
        items = assert_paginated_list(r, min_items=1)
        # 每个商品有必需字段
        for p in items:
            assert {"id", "name", "price", "stock"} <= set(p.keys())

    @allure.title("取存在的商品 → 200")
    @pytest.mark.smoke
    def test_get_existing_product(self, raw_client: HttpClient):
        product_api = ProductAPI(raw_client)
        pid = product_api.list().json()[0]["id"]
        r = product_api.get(pid)
        attach_response(r)
        assert_status(r, 200)
        assert r.json()["id"] == pid

    @allure.title("取不存在商品 → 404")
    def test_get_nonexistent(self, raw_client: HttpClient):
        product_api = ProductAPI(raw_client)
        r = product_api.get(99999)
        attach_response(r)
        assert_status(r, 404)


@allure.feature("商品接口")
@allure.story("权限")
class TestProductAdmin:
    @allure.title("无 token 建商品 → 401")
    def test_create_no_token(self, raw_client: HttpClient):
        # 注意：ProductAPI.create 内部 auth=True，但因为 token_manager=None，不会带 Bearer
        # 用 raw_client 没 token_manager → 等同于无 Bearer 请求 → 401
        product_api = ProductAPI(raw_client)
        r = product_api.create("X", 1.0)
        attach_response(r)
        assert_status(r, 401)

    @allure.title("普通用户建商品 → 403")
    def test_create_as_user(self, raw_client: HttpClient):
        # 注册普通用户，构造带该用户 token 的 client
        auth_api = AuthAPI(raw_client)
        cred = auth_api.random_credential()
        auth_api.register(cred["username"], cred["email"], cred["password"])
        token = auth_api.login(cred["username"], cred["password"]).json()["access_token"]
        # 用带普通用户 token 的 client 建商品 → 403
        from tests.api_client_helper import make_user_client
        client = make_user_client(raw_client.base_url, token, raw_client.timeout)
        product_api = ProductAPI(client)
        r = product_api.create("X", 1.0)
        attach_response(r)
        assert_status(r, 403)
        client.close()

    @allure.title("admin 建商品 → 201")
    @pytest.mark.smoke
    def test_create_as_admin(self, api_client: HttpClient):
        # api_client 默认走 admin（见 conftest token_manager 用 settings.username=admin）
        product_api = ProductAPI(api_client)
        p = ProductData().with_name(f"admin建_{__import__('secrets').token_hex(3)}").build()
        r = product_api.create(**p)
        attach_response(r)
        assert_status(r, 201)
        new_id = r.json()["id"]
        assert r.json()["name"] == p["name"]
        # 清理：admin 删掉
        product_api.delete(new_id)

    @allure.title("admin 更新商品 → 200")
    def test_update_as_admin(self, api_client: HttpClient):
        product_api = ProductAPI(api_client)
        p = ProductData().build()
        r = product_api.create(**p)
        pid = r.json()["id"]
        up = product_api.update(pid, {"price": 99.9, "stock": 7})
        attach_response(up)
        assert_status(up, 200)
        assert up.json()["price"] == 99.9
        assert up.json()["stock"] == 7
        product_api.delete(pid)

    @allure.title("admin 删除商品 → 204；再查 → 404")
    def test_delete_as_admin(self, api_client: HttpClient):
        product_api = ProductAPI(api_client)
        pid = product_api.create(**ProductData().build()).json()["id"]
        d = product_api.delete(pid)
        assert_status(d, 204)
        assert_status(product_api.get(pid), 404)
