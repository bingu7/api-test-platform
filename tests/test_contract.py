"""接口契约测试（real 环境）—— 以 OpenAPI/Swagger 为契约。

学习重点：
- 接口契约 = OpenAPI 文档里声明的端点/方法/状态码/响应结构。
- 契约测试回答：「实现有没有偏离文档？」
- 这里用 FastAPI 自动生成的 /openapi.json 作为契约源，逐端点拉取响应校验。

对比单元/功能测试：
- 功能测试：给定输入，期望某输出（验业务逻辑）
- 契约测试：响应结构必须符合契约声明的 schema（验 API 没漂移）
"""
from __future__ import annotations

import json

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_status, attach_response

pytestmark = [pytest.mark.backend, pytest.mark.contract]


@allure.feature("契约测试")
@allure.story("OpenAPI 规范")
class TestOpenAPIContract:
    @allure.title("/openapi.json 可获取且结构合法")
    @pytest.mark.smoke
    def test_openapi_available(self, raw_client: HttpClient):
        r = raw_client.get("/openapi.json", auth=False)
        attach_response(r)
        assert_status(r, 200)
        spec = r.json()
        assert spec["openapi"].startswith("3."), f"应为 OpenAPI 3.x，实际 {spec['openapi']}"
        assert "paths" in spec and "components" in spec
        allure.attach(json.dumps(spec["info"], ensure_ascii=False), name="API info",
                      attachment_type=allure.attachment_type.JSON)

    @allure.title("关键端点都在契约里声明")
    @pytest.mark.smoke
    def test_key_endpoints_declared(self, raw_client: HttpClient):
        spec = raw_client.get("/openapi.json", auth=False).json()
        paths = spec["paths"]
        expected = [
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/me",
            "/api/products",
            "/api/orders",
            "/api/payment/pay",
            "/api/payment/refund",
            "/health",
        ]
        missing = [p for p in expected if p not in paths]
        assert not missing, f"缺失端点声明: {missing}"

    @allure.title("每个鉴权端点声明了安全要求（security 或 401/403 响应）")
    def test_protected_endpoints_declare_auth(self, raw_client: HttpClient):
        spec = raw_client.get("/openapi.json", auth=False).json()
        paths = spec["paths"]
        # 这几个端点应鉴权——契约里要能看到安全要求或鉴权失败响应
        secured = ["/api/auth/me", "/api/orders", "/api/payment/pay"]
        for ep in secured:
            if ep not in paths:
                continue
            for method, op in paths[ep].items():
                if method == "parameters":
                    continue
                # 合格条件（任一）：
                # 1. 声明了 security 依赖安全方案
                # 2. 声明了 401 或 403 响应码
                has_security = bool(op.get("security"))
                has_auth_response = "401" in op.get("responses", {}) or "403" in op.get("responses", {})
                assert has_security or has_auth_response, (
                    f"{ep.upper()} 未声明任何鉴权要求（security / 401 / 403）"
                )


@allure.feature("契约测试")
@allure.story("响应结构符合契约")
class TestResponseSchema:
    @allure.title("商品列表是数组、每项有 id/name/price/stock")
    @pytest.mark.smoke
    def test_products_schema(self, raw_client: HttpClient):
        r = raw_client.get("/api/products", auth=False)
        assert_status(r, 200)
        payload = r.json()
        assert isinstance(payload, list), "应为数组"
        for p in payload:
            assert {"id", "name", "price", "stock"} <= set(p.keys()), f"缺字段: {p}"

    @allure.title("登录成功响应含 access_token/token_type/expires_in")
    def test_login_token_schema(self, raw_client: HttpClient):
        r = raw_client.post("/api/auth/login", auth=False,
                             json={"username": "admin", "password": "admin123"})
        assert_status(r, 200)
        p = r.json()
        for k in ("access_token", "token_type", "expires_in"):
            assert k in p, f"登录响应缺字段 {k}"

    @allure.title("错误响应统一含 detail 字段（FastAPI 约定）")
    def test_error_shape(self, raw_client: HttpClient):
        # 404
        r = raw_client.get("/api/products/99999", auth=False)
        assert_status(r, 404)
        assert "detail" in r.json()
        # 422 校验错误
        r = raw_client.post("/api/auth/register", auth=False,
                             json={"username": "x", "email": "bad", "password": "12345"})
        assert_status(r, 422)
        # FastAPI 422 形状是 {detail: [...]}
        assert "detail" in r.json()
