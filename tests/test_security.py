"""接口安全测试维度（real 环境）。

学习重点——接口安全测试该覆盖什么：
- 鉴权：无 token → 401、伪造/过期 token → 401
- 授权（IDOR/越权）：A 用户用 B 的 order_id 查询/操作 → 403
- 权限提升：普通用户调 admin 接口 → 403
- 敏感信息泄露：响应不含密码哈希 / 无关用户信息
- SQL 注入：恶意 payload 作为查询参数 → 不应击穿 DB / 应被参数化消化
- 输入边界：超长字符串、特殊字符不导致 500

这是面试里能让人眼前一亮的维度——多数人只测「正不正常」，不测「安不安全」。
"""
from __future__ import annotations

import secrets

import allure
import pytest

from apis import AuthAPI, OrderAPI, ProductAPI
from core.base_request import HttpClient
from utils.assert_helpers import assert_detail, assert_status, attach_response
from tests.api_client_helper import make_user_client

pytestmark = [pytest.mark.backend, pytest.mark.security]


def _register_and_login(raw_client, username=None):
    """注册一个普通用户并返回 (token, username)。任一环节失败立即断言，不放行到后面 KeyError。"""
    auth = AuthAPI(raw_client)
    cred = auth.random_credential()
    if username:
        cred["username"] = username
    reg = auth.register(cred["username"], cred["email"], cred["password"])
    assert reg.status_code == 201, f"注册失败: {reg.status_code} {reg.text[:200]}"
    r = auth.login(cred["username"], cred["password"])
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"], cred["username"]


@allure.feature("接口安全")
@allure.story("鉴权")
class TestAuthSecurity:
    @allure.title("无 token 访问受保护端点 → 401")
    @pytest.mark.smoke
    def test_no_token_401(self, raw_client: HttpClient):
        for ep in ["/api/auth/me", "/api/orders", "/api/payment/status/SEED_ORD_001"]:
            r = raw_client.get(ep)  # 不挂 Bearer
            assert r.status_code == 401, f"{ep} 应 401，实际 {r.status_code}"

    @allure.title("伪造 token → 401")
    def test_forged_token(self, raw_client: HttpClient):
        r = raw_client.get("/api/auth/me", auth=False,
                           headers={"Authorization": "Bearer not.a.real.jwt"})
        attach_response(r)
        assert_status(r, 401)

    @allure.title("Bearer 后为空 → 401")
    def test_empty_bearer(self, raw_client: HttpClient):
        r = raw_client.get("/api/auth/me", auth=False, headers={"Authorization": "Bearer "})
        assert_status(r, 401)

    @allure.title("接口密钥从不出现在响应中")
    def test_no_password_leakage(self, raw_client: HttpClient):
        auth = AuthAPI(raw_client)
        cred = auth.random_credential()
        r = auth.register(cred["username"], cred["email"], cred["password"])
        payload = r.json()
        assert "password" not in payload, "响应泄漏了 password"
        assert "hashed_password" not in payload, "响应泄漏了 hashed_password"

    @allure.title("不同用户登录返回不同 token")
    def test_tokens_are_unique(self, raw_client: HttpClient):
        auth = AuthAPI(raw_client)
        c1 = auth.random_credential(); auth.register(**c1)
        c2 = auth.random_credential(); auth.register(**c2)
        t1 = auth.login(c1["username"], c1["password"]).json()["access_token"]
        t2 = auth.login(c2["username"], c2["password"]).json()["access_token"]
        assert t1 != t2


@allure.feature("接口安全")
@allure.story("越权 (IDOR)")
class TestIDOR:
    @allure.title("A 用户不能查 B 的订单 → 403")
    @pytest.mark.smoke
    def test_cannot_read_others_order(self, raw_client: HttpClient):
        # 用户 A 下一个单
        owner_token, _ = _register_and_login(raw_client, f"idor_owner_{secrets.token_hex(3)}")
        owner_client = make_user_client(raw_client.base_url, owner_token, raw_client.timeout)
        oid = f"IDOR_{secrets.token_hex(4)}"
        OrderAPI(owner_client).create(oid, 10.0)

        # 用户 B 尝试查 → 403
        other_token, _ = _register_and_login(raw_client, f"idor_other_{secrets.token_hex(3)}")
        other_client = make_user_client(raw_client.base_url, other_token, raw_client.timeout)
        r = other_client.get(f"/api/orders/{oid}")
        attach_response(r)
        assert_status(r, 403)
        owner_client.close(); other_client.close()

    @allure.title("A 用户不能取消 B 的订单 → 403")
    def test_cannot_cancel_others_order(self, raw_client: HttpClient):
        owner_token, _ = _register_and_login(raw_client, f"idor_a_{secrets.token_hex(3)}")
        owner_client = make_user_client(raw_client.base_url, owner_token, raw_client.timeout)
        oid = f"IDORC_{secrets.token_hex(4)}"
        OrderAPI(owner_client).create(oid, 10.0)

        other_token, _ = _register_and_login(raw_client, f"idor_b_{secrets.token_hex(3)}")
        other_client = make_user_client(raw_client.base_url, other_token, raw_client.timeout)
        r = other_client.put(f"/api/orders/{oid}/cancel")
        attach_response(r)
        assert_status(r, 403)
        owner_client.close(); other_client.close()

    @allure.title("A 不能为 B 的订单支付/退款 → 403")
    def test_cannot_pay_others_order(self, raw_client: HttpClient):
        owner_token, _ = _register_and_login(raw_client, f"idor_p_{secrets.token_hex(3)}")
        owner_client = make_user_client(raw_client.base_url, owner_token, raw_client.timeout)
        oid = f"IDORP_{secrets.token_hex(4)}"
        OrderAPI(owner_client).create(oid, 10.0)

        other_token, _ = _register_and_login(raw_client, f"idor_q_{secrets.token_hex(3)}")
        other_client = make_user_client(raw_client.base_url, other_token, raw_client.timeout)
        from apis import PaymentAPI
        r = PaymentAPI(other_client).pay(oid)
        attach_response(r)
        assert_status(r, 403)
        owner_client.close(); other_client.close()


@allure.feature("接口安全")
@allure.story("权限隔离")
class TestAuthorization:
    @allure.title("普通用户建/删商品 → 403")
    @pytest.mark.smoke
    def test_user_cannot_admin_product(self, raw_client: HttpClient):
        token, _ = _register_and_login(raw_client, f"perm_u_{secrets.token_hex(3)}")
        user_client = make_user_client(raw_client.base_url, token, raw_client.timeout)
        product_api = ProductAPI(user_client)
        # 建 → 403
        r = product_api.create("X", 1.0)
        attach_response(r)
        assert_status(r, 403)
        # 删（取一个存在的种子商品 id） → 403
        first_id = ProductAPI(raw_client).list().json()[0]["id"]
        r = product_api.delete(first_id)
        assert_status(r, 403)
        user_client.close()


@allure.feature("接口安全")
@allure.story("SQL 注入")
class TestSQLInjection:
    @allure.title("用户名字段传 SQL 注入 payload → 不击穿 DB、正常报 401/409/未注册")
    @pytest.mark.parametrize("payload", [
        "' OR '1'='1",
        "admin'--",
        "'; DROP TABLE users;--",
        "admin' UNION SELECT * FROM users--",
    ])
    def test_login_sql_injection(self, raw_client: HttpClient, payload):
        auth = AuthAPI(raw_client)
        r = auth.login(payload, "anything")
        attach_response(r)
        # 应 401（用户名或密码错误），DB 没被击穿
        assert_status(r, 401)
        # 体积表还在（没被 DROP）
        assert raw_client.get("/api/products").status_code == 200

    @allure.title("商品 id 注入应被拒绝（类型校验）")
    def test_product_id_injection(self, raw_client: HttpClient):
        # FastAPI 路径参数声明为 int，传字符串会被它直接拒绝 → 422，不进 DB
        r = raw_client.get("/api/products/1 OR 1=1")
        assert r.status_code in (422, 404)


@allure.feature("接口安全")
@allure.story("健壮性")
class TestInputRobustness:
    @allure.title("超长用户名 → 不 500（422 或正常）")
    def test_very_long_username(self, raw_client: HttpClient):
        auth = AuthAPI(raw_client)
        long_name = "a" * 500
        r = auth.register(long_name, "long@example.com", "Passw0rd!")
        assert r.status_code != 500, "超长输入应被校验拒绝，不该崩服务"

    @allure.title("请求体为非法 JSON 不导致 500")
    def test_malformed_json(self, raw_client: HttpClient):
        r = raw_client.post("/api/auth/register", auth=False,
                            headers={"Content-Type": "application/json"},
                            data="{not json")
        assert r.status_code in (400, 422), f"非法 JSON 应 400/422，实际 {r.status_code}"
