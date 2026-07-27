"""
HTTP 客户端封装。

设计要点（学这个就够用）：
1. Session 复用 + Retry
2. trust_env=False，避免本机代理污染
3. auth=True/False：鉴权接口与登录/公开接口分流
4. 便捷 get/post/put/delete
"""
from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.token_manager import TokenManager
from utils.logger import get_logger

logger = get_logger("http")


class HttpClient:
    def __init__(
        self,
        base_url: str,
        token_manager: TokenManager | None = None,
        timeout: tuple[float, float] = (5, 15),
        retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.token_manager = token_manager
        self.timeout = timeout
        self.session = self._create_session(retries)

    def _create_session(self, retries: int) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        # 不含 504：业务约定返回的「超时」若进重试，会把 1 次请求变成多次。
        retry = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503],
            allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "PATCH"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _build_headers(self, auth: bool, extra: dict | None) -> dict[str, str]:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if auth and self.token_manager is not None:
                headers["Authorization"] = f"Bearer {self.token_manager.get_token()}"
            if extra:
                headers.update(extra)
            return headers

    def request(
            self,
            method: str,
            endpoint: str,
            *,
            auth: bool = True,
            headers: dict | None = None,
            timeout: tuple[float, float] | None = None,
            **kwargs: Any,
        ) -> requests.Response:
            """
            要求 auth=True 自动带 Bearer；登录/公开接口请传 False。
            当 auth=True 且收到 401 时，自动 invalidate token 并重试一次（防死循环）。
            """
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint
            url = f"{self.base_url}{endpoint}"
            final_headers = self._build_headers(auth=auth, extra=headers)
            final_timeout = timeout or self.timeout

            logger.debug("%s %s auth=%s", method.upper(), url, auth)

            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=final_headers,
                timeout=final_timeout,
                **kwargs,
            )

            # 401 自动重登（仅当需要鉴权且 TokenManager 可用时）
            if auth and response.status_code == 401 and self.token_manager is not None:
                logger.info("收到 401，尝试刷新 token 并重试")
                self.token_manager.invalidate()
                retry_headers = self._build_headers(auth=True, extra=headers)
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    headers=retry_headers,
                    timeout=final_timeout,
                    **kwargs,
                )

            return response

    def get(self, endpoint: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", endpoint, **kwargs)

    def close(self) -> None:
        self.session.close()


# 兼容旧名称
BaseRequest = HttpClient
