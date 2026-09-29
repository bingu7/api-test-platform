"""测试辅助：构造一个带任意用户 JWT 的 HttpClient。

为什么需要：
- api_client 默认走 settings 里的 admin，但有些用例需要「普通用户 token」视角（如 IDOR、权限测试）。
- 这个 helper 拿到一个 JWT，造一个「永远带这个 token」的轻量 HttpClient，
  既不受 TokenManager 缓存影响，也不污染 session 级 api_client。

实现：把 HttpClient 的 _build_headers 重写以注射固定 token，简单可控。
"""
from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.logger import get_logger

logger = get_logger("user_client")


class _BearerInjectorSession:
    """代理 Session：所有请求自动加 Authorization: Bearer <token>。"""

    def __init__(self, session: requests.Session, token: str):
        object.__setattr__(self, "_session", session)
        object.__setattr__(self, "_token", token)

    def request(self, method: str, url: str, **kwargs: Any):
        headers = kwargs.setdefault("headers", {})
        headers["Authorization"] = f"Bearer {object.__getattribute__(self, '_token')}"
        return object.__getattribute__(self, "_session").request(method=method, url=url, **kwargs)

    def close(self):
        object.__getattribute__(self, "_session").close()


def make_user_client(base_url: str, token: str, timeout=(5, 15)) -> requests.Session:
    """造一个 `http://base+endpoint` 风格、自动带 Bearer 的 Session（不是 HttpClient，够用即可）。

    返回带 .base_url / .request(...) / .get/post/put/delete(patch) / .close() 的轻量对象。
    """
    sess = requests.Session()
    sess.trust_env = False
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503],
                  allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "PATCH"]), raise_on_status=False)
    sess.mount("http://", HTTPAdapter(max_retries=retry))
    sess.mount("https://", HTTPAdapter(max_retries=retry))

    class UserClient:
        def __init__(self):
            self.base_url = base_url.rstrip("/")
            self.timeout = timeout
            self._session = _BearerInjectorSession(sess, token)

        def _url(self, ep: str) -> str:
            # ep 可能以 / 开头，避免双斜杠
            if not ep.startswith("/"):
                ep = "/" + ep
            return self.base_url + ep

        def request(self, method, endpoint, **kw):
            kw.pop("auth", None)  # HttpClient 风格的 auth 参数——本 client 已注入固定 token，忽略它
            kw.setdefault("timeout", self.timeout)
            return self._session.request(method.upper(), self._url(endpoint), **kw)

        def get(self, ep, **kw): return self.request("GET", ep, **kw)
        def post(self, ep, **kw): return self.request("POST", ep, **kw)
        def put(self, ep, **kw): return self.request("PUT", ep, **kw)
        def delete(self, ep, **kw): return self.request("DELETE", ep, **kw)
        def patch(self, ep, **kw): return self.request("PATCH", ep, **kw)

        def close(self): self._session.close()

    return UserClient()
