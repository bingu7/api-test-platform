"""鉴权接口封装。

对应后端 apps/backend/routers/auth.py 的端点：
- POST /api/auth/register   注册
- POST /api/auth/login       登录（返回 JWT）
- GET  /api/auth/me          取当前用户（需 Bearer）
"""
from __future__ import annotations

import secrets
from typing import Any

from requests import Response

from core.base_request import HttpClient


class AuthAPI:
    """鉴权接口封装类。所有方法返回 requests.Response。"""

    def __init__(self, client: HttpClient):
        self.client = client

    def register(self, username: str, email: str, password: str, **kw: Any) -> Response:
        """注册新用户（不带 token，纯公开接口 → auth=False）。"""
        return self.client.post(
            "/api/auth/register",
            auth=False,
            json={"username": username, "email": email, "password": password},
            **kw,
        )

    def login(self, username: str, password: str, **kw: Any) -> Response:
        """登录，后端返回 access_token（JWT）。"""
        return self.client.post(
            "/api/auth/login",
            auth=False,
            json={"username": username, "password": password},
            **kw,
        )

    def login_raw(self, username: str, password: str, **kw: Any) -> Response:
        """与 login 相同，显式名提醒「裸请求、不带 auth」——便于在负向用例里语义清晰。"""
        return self.login(username, password, **kw)

    def get_me(self, **kw: Any) -> Response:
        """取当前登录用户信息（需 Bearer token，auth=True）。"""
        return self.client.get("/api/auth/me", auth=True, **kw)

    def get_me_raw(self, token: str | None = None, **kw: Any) -> Response:
        """不带 token 访问 /me（用于测 401）。若传 token 则手挂 Authorization 头。"""
        kw.pop("auth", None)  # 防止上层误传 auth 占用位置参数
        headers = kw.pop("headers", None) or {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.get("/api/auth/me", auth=False, headers=headers, **kw)

    @staticmethod
    def random_credential() -> dict[str, str]:
        """生成一组随机、唯一的注册凭证（避免重复用例撞用户名）。"""
        suffix = secrets.token_hex(6)
        return {
            "username": f"user_{suffix}",
            "email": f"user_{suffix}@example.com",
            "password": "Passw0rd!",
        }
