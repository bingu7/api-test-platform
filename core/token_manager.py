"""Token 管理：缓存 + 过期刷新 + 明确失败异常。"""
from __future__ import annotations

import time
from typing import Any

import requests

from utils.logger import get_logger

logger = get_logger("token")


class TokenError(RuntimeError):
    """获取 / 解析 token 失败。"""


class TokenManager:
    def __init__(
        self,
        auth_url: str,
        credentials: dict[str, Any],
        timeout: tuple[float, float] = (5, 15),
        token_field: str = "access_token",
        expires_field: str = "expires_in",
        skew_seconds: int = 60,
    ):
        self.auth_url = auth_url
        self.credentials = credentials
        self.timeout = timeout
        self.token_field = token_field
        self.expires_field = expires_field
        self.skew_seconds = skew_seconds
        self._token: str | None = None
        self._expires_at: float = 0
        self._session = requests.Session()
        self._session.trust_env = False

    def invalidate(self) -> None:
        """强制下次 get_token 重新登录。"""
        self._token = None
        self._expires_at = 0

    def _fetch_token(self) -> dict[str, Any]:
        response = self._session.post(
            self.auth_url, json=self.credentials, timeout=self.timeout
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise TokenError(
                f"获取 token 失败: HTTP {response.status_code}, body={response.text[:300]}"
            ) from e

        try:
            data = response.json()
        except ValueError as e:
            raise TokenError(
                f"获取 token 失败: 响应非 JSON, body={response.text[:300]}"
            ) from e

        if self.token_field not in data:
            raise TokenError(
                f"获取 token 失败: 响应缺少 {self.token_field}, body={data}"
            )

        expires_in = int(data.get(self.expires_field, 3600))
        return {
            "token": data[self.token_field],
            "expires_at": time.time() + expires_in - self.skew_seconds,
        }

    def get_token(self) -> str:
        if not self._token or time.time() >= self._expires_at:
            result = self._fetch_token()
            self._token = result["token"]
            self._expires_at = result["expires_at"]
            logger.info("token 已刷新，有效期至 %s", time.ctime(self._expires_at))
        return self._token
