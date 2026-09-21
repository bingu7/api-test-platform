"""鉴权接口 PO 测试（real 环境）。

用 apis/auth_api.py 封装层调接口，断言留在这层。学 PO 模式：
- 调方法很简单（auth_api.register(...)）
- 断言显式写在这层（assert_status / 业务校验）
"""
from __future__ import annotations

import allure
import pytest

from apis import AuthAPI
from core.base_request import HttpClient
from data.builders import UserData
from utils.assert_helpers import assert_detail, assert_status, attach_response

pytestmark = [pytest.mark.backend]


@allure.feature("鉴权接口")
@allure.story("注册")
class TestRegister:
    @allure.title("正常注册")
    @pytest.mark.smoke
    def test_register_success(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        cred = auth_api.random_credential()
        r = auth_api.register(cred["username"], cred["email"], cred["password"])
        attach_response(r)
        assert_status(r, 201)
        payload = r.json()
        assert payload["username"] == cred["username"]
        assert payload["email"] == cred["email"]
        assert payload["role"] == "user"
        # 安全：响应不应含密码字段（明文或哈希都不应出现）
        assert "hashed_password" not in payload
        assert "password" not in payload

    @allure.title("重复用户名注册 → 400")
    def test_register_duplicate_username(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        cred = auth_api.random_credential()
        auth_api.register(cred["username"], cred["email"], cred["password"])
        r = auth_api.register(cred["username"], "other@example.com", cred["password"])
        attach_response(r)
        assert_status(r, 400)
        assert_detail(r, "用户名已存在")

    @allure.title("短密码 → 422")
    def test_register_short_password(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        r = auth_api.register("u_short", "s@example.com", "123")  # <6
        attach_response(r)
        assert_status(r, 422)

    @allure.title("非法邮箱 → 422")
    def test_register_bad_email(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        r = auth_api.register("u_badmail", "not-an-email", "Passw0rd!")
        attach_response(r)
        assert_status(r, 422)

    @allure.title("用 Builder 造随机凭证注册（数据构造器演示）")
    @pytest.mark.smoke
    def test_register_via_builder(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        user = UserData().with_username(f"builder_{__import__('secrets').token_hex(3)}").build()
        r = auth_api.register(user["username"], user["email"], user["password"])
        assert_status(r, 201)


@allure.feature("鉴权接口")
@allure.story("登录")
class TestLogin:
    @allure.title("用种子 admin 登录成功 → 200")
    @pytest.mark.smoke
    def test_login_admin_success(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        r = auth_api.login("admin", "admin123")
        attach_response(r)
        assert_status(r, 200)
        payload = r.json()
        assert "access_token" in payload and len(payload["access_token"]) > 10
        assert payload["token_type"] == "bearer"
        assert payload["expires_in"] > 0

    @allure.title("密码错误 → 401 且不泄露用户是否存在")
    def test_login_wrong_password(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        r1 = auth_api.login("admin", "wrong")
        r2 = auth_api.login("no_such_user", "wrong")
        attach_response(r1); attach_response(r2)
        assert_status(r1, 401)
        assert_status(r2, 401)
        # 关键：两种失败文案必须一致（消除用户枚举）
        assert r1.json()["detail"] == r2.json()["detail"]

    @allure.title("登录拿 token 后取 me → 200")
    @pytest.mark.smoke
    def test_login_then_me(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        # 注册一个用户再登录
        cred = auth_api.random_credential()
        auth_api.register(cred["username"], cred["email"], cred["password"])
        r = auth_api.login(cred["username"], cred["password"])
        token = r.json()["access_token"]
        # 手挂 token 取 me
        me = auth_api.get_me_raw(token=token, auth=None)  # 注意：get_me_raw 不走 client auth
        assert_status(me, 200)
        assert me.json()["username"] == cred["username"]

    @allure.title("无 token 访问 me → 401")
    def test_me_no_token(self, raw_client: HttpClient):
        auth_api = AuthAPI(raw_client)
        r = auth_api.get_me_raw()
        assert_status(r, 401)
