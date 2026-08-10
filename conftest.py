"""
Pytest 全局 fixture。

分层：
- settings: 配置
- is_mock_env: dev = Mock模式, test/staging = 真实服务模式
- mock_db / mock_server: 仅 dev 环境启用
- base_url: dev→Mock, test/staging→真实服务（jsonplaceholder 等）
- api_client / raw_client: 统一的 HTTP 客户端

环境切换：
  $env:TEST_ENV="dev"    → 本地 Mock（默认）
  $env:TEST_ENV="test"   → jsonplaceholder.typicode.com（公开免费 API）
  $env:TEST_ENV="staging" → 自定义 BASE_URL 覆盖
"""
from __future__ import annotations

import os
import sys

import pytest

from config.settings import Settings, get_settings
from core.base_request import HttpClient
from core.mock_db import MockDB
from core.mock_server import MockServer, start_mock_server
from core.token_manager import TokenManager
from utils.logger import get_logger
from utils.paths import ALLURE_RESULTS_DIR, PROJECT_ROOT

logger = get_logger("conftest")


def pytest_sessionstart(session: pytest.Session) -> None:
    ALLURE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    env_file = ALLURE_RESULTS_DIR / "environment.properties"
    lines = [
        f"ENV={settings.env}",
        f"BaseURL={settings.base_url}",
        f"PythonPath={sys.executable}",
        f"ProjectRoot={PROJECT_ROOT}",
        f"CI={os.getenv('CI', os.getenv('JENKINS_URL', 'local'))}",
        f"BuildUrl={os.getenv('BUILD_URL', '')}",
        f"JobName={os.getenv('JOB_NAME', '')}",
    ]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pytest_collection_modifyitems(config, items):
    """环境过滤：dev 只跑 Mock 业务用例（跳过 real_env）；非 dev 只跑 real_env 用例。"""
    settings = get_settings()
    if settings.env == "dev":
        skip_real = pytest.mark.skip(reason="dev 环境不跑真实环境用例（切换到 test 运行）")
        for item in items:
            if "real_env" in item.keywords:
                item.add_marker(skip_real)
    else:
        skip_mock = pytest.mark.skip(reason="非 Mock 环境不跑业务用例（切换到 dev 运行）")
        for item in items:
            if "real_env" not in item.keywords:
                item.add_marker(skip_mock)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def is_mock_env(settings: Settings) -> bool:
    return settings.env == "dev"


# ── Mock 层（仅 dev 环境） ──
@pytest.fixture(scope="session")
def mock_db(is_mock_env: bool) -> MockDB | None:
    if not is_mock_env:
        return None
    return MockDB()


@pytest.fixture(scope="session")
def mock_server(is_mock_env: bool, settings: Settings, mock_db: MockDB | None) -> MockServer | None:
    if not is_mock_env:
        logger.info("TEST_ENV=%s → 不启动 Mock，直连 %s", settings.env, settings.base_url)
        return None
    server = MockServer(host=settings.mock_host, port=None, db=mock_db, login_rate_limit=0)
    return server.start()


# ── URL 层 ──
@pytest.fixture(scope="session")
def base_url(is_mock_env: bool, mock_server: MockServer | None, settings: Settings) -> str:
    return (mock_server and mock_server.base_url) or settings.base_url


@pytest.fixture(scope="session")
def auth_url(is_mock_env: bool, mock_server: MockServer | None, settings: Settings) -> str:
    return (mock_server and mock_server.auth_url) or settings.auth_url


# ── Token（仅 dev 需要登录） ──
@pytest.fixture(scope="session")
def token_manager(is_mock_env: bool, auth_url: str, settings: Settings) -> TokenManager | None:
    if not is_mock_env:
        # 真实服务（jsonplaceholder）无鉴权，不上 TokenManager
        return None
    return TokenManager(
        auth_url=auth_url,
        credentials={"username": settings.username, "password": settings.password},
        timeout=settings.timeout,
    )


# ── HTTP 客户端 ──
@pytest.fixture(scope="session")
def api_client(
    base_url: str,
    token_manager: TokenManager | None,
    settings: Settings,
) -> HttpClient:
    client = HttpClient(
        base_url=base_url,
        token_manager=token_manager,
        timeout=settings.timeout,
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def raw_client(base_url: str, settings: Settings) -> HttpClient:
    client = HttpClient(
        base_url=base_url,
        token_manager=None,
        timeout=settings.timeout,
    )
    yield client
    client.close()


# ── 兼容旧 fixture 名 ──
@pytest.fixture(scope="session")
def config(settings: Settings) -> Settings:
    return settings


@pytest.fixture(scope="session")
def base_request(api_client: HttpClient) -> HttpClient:
    return api_client