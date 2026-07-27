"""
多环境配置。

优先级：环境变量 > 各环境默认值。
- TEST_ENV: dev | test | staging
- BASE_URL / AUTH_URL / API_USERNAME / API_PASSWORD / CONNECT_TIMEOUT / READ_TIMEOUT

注意：不要用 USERNAME 作为环境变量名——Windows 系统自带 USERNAME=当前登录用户，会污染配置。
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return value.strip()


@dataclass(frozen=True)
class Settings:
    """不可变配置对象，测试中只读。"""

    env: str
    app_name: str
    base_url: str
    auth_url: str
    username: str
    password: str
    connect_timeout: float
    read_timeout: float
    # Mock 默认监听地址（Windows 上优先 127.0.0.1，避免 localhost 解析慢）
    mock_host: str = "127.0.0.1"

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.connect_timeout, self.read_timeout)


# 各环境默认值（学习/本地 Mock 用；真实环境请用环境变量覆盖）
_DEFAULTS: dict[str, dict] = {
    "dev": {
        "base_url": "http://127.0.0.1:5000",
        "auth_url": "http://127.0.0.1:5000/api/login",
        "username": "admin",
        "password": "123456",
    },
    "test": {
        "base_url": "https://jsonplaceholder.typicode.com",
        "auth_url": "https://jsonplaceholder.typicode.com/posts",  # 无真实 auth，用 posts 代替
        "username": "",   # JSONPlaceholder 无鉴权
        "password": "",   # JSONPlaceholder 无鉴权
    },
    "staging": {
        "base_url": "https://staging.example.com",
        "auth_url": "https://staging.example.com/auth/login",
        "username": "staging_user",
        "password": "staging_pass",
    },
}


def get_settings(env: str | None = None) -> Settings:
    env_name = (env or _env("TEST_ENV", "dev") or "dev").lower()
    if env_name not in _DEFAULTS:
        raise ValueError(f"未知环境: {env_name}，可选: {list(_DEFAULTS.keys())}")

    defaults = _DEFAULTS[env_name]
    return Settings(
        env=env_name,
        app_name=_env("APP_NAME", "api-test-platform") or "api-test-platform",
        base_url=_env("BASE_URL", defaults["base_url"]) or defaults["base_url"],
        auth_url=_env("AUTH_URL", defaults["auth_url"]) or defaults["auth_url"],
        # 切勿使用 USERNAME：Windows 会注入当前系统用户名
        username=_env("API_USERNAME", defaults["username"]) or defaults["username"],
        password=_env("API_PASSWORD", defaults["password"]) or defaults["password"],
        connect_timeout=float(_env("CONNECT_TIMEOUT", "5") or "5"),
        read_timeout=float(_env("READ_TIMEOUT", "15") or "15"),
        mock_host=_env("MOCK_HOST", "127.0.0.1") or "127.0.0.1",
    )


# 兼容旧调用名
def get_config(env: str | None = None) -> Settings:
    return get_settings(env)
