"""
Pytest 全局 fixture。

分层：
- settings: 配置
- mock_server: session 级共享 Mock（整次测试只起一次）
- api_client: 带 Token 的 HttpClient（指向 Mock）
- raw_client: 不带 Token 的 HttpClient（登录/公开接口）
"""
from __future__ import annotations

import os
import sys

import pytest

from config.settings import Settings, get_settings
from core.base_request import HttpClient
from core.mock_server import MockServer, start_mock_server
from core.token_manager import TokenManager
from utils.paths import ALLURE_RESULTS_DIR, PROJECT_ROOT


def pytest_sessionstart(session: pytest.Session) -> None:
    """为 Allure 写入 environment.properties（Jenkins/本地报告里可见环境信息）。"""
    ALLURE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    env_file = ALLURE_RESULTS_DIR / "environment.properties"
    lines = [
        f"ENV={settings.env}",
        f"MockHost={settings.mock_host}",
        f"PythonPath={sys.executable}",
        f"ProjectRoot={PROJECT_ROOT}",
        f"CI={os.getenv('CI', os.getenv('JENKINS_URL', 'local'))}",
        f"BuildUrl={os.getenv('BUILD_URL', '')}",
        f"JobName={os.getenv('JOB_NAME', '')}",
    ]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def mock_server(settings: Settings) -> MockServer:
    """整个测试会话共用一个 Mock，自动分配空闲端口。"""
    server = start_mock_server(host=settings.mock_host, port=None)
    yield server
    server.stop()


@pytest.fixture(scope="session")
def token_manager(mock_server: MockServer, settings: Settings) -> TokenManager:
    return TokenManager(
        auth_url=mock_server.auth_url,
        credentials={"username": settings.username, "password": settings.password},
        timeout=settings.timeout,
    )


@pytest.fixture(scope="session")
def api_client(
    mock_server: MockServer,
    token_manager: TokenManager,
    settings: Settings,
) -> HttpClient:
    """需要鉴权的接口用这个（默认 auth=True）。"""
    client = HttpClient(
        base_url=mock_server.base_url,
        token_manager=token_manager,
        timeout=settings.timeout,
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def raw_client(mock_server: MockServer, settings: Settings) -> HttpClient:
    """登录等公开接口用这个（调用时 auth=False）。"""
    client = HttpClient(
        base_url=mock_server.base_url,
        token_manager=None,
        timeout=settings.timeout,
    )
    yield client
    client.close()


# 兼容旧 fixture 名
@pytest.fixture(scope="session")
def config(settings: Settings) -> Settings:
    return settings


@pytest.fixture(scope="session")
def base_request(api_client: HttpClient) -> HttpClient:
    return api_client
