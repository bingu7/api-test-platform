"""Pytest 全局 fixture。

分层：
- settings: 配置（dev=Mock / real=FastAPI后端 / test=jsonplaceholder / staging=自定义）
- is_mock_env: 仅 dev 走 Flask Mock
- is_backend_env: 仅 real 走 FastAPI 后端
- mock_db / mock_server: 仅 dev 启用
- backend_server: 仅 real 启用（子进程起 uvicorn）
- base_url / auth_url: dev→Mock, real→后端, test/staging→真实服务
- api_client / raw_client: 统一 HTTP 客户端（带/不带 Token）

环境切换：
  $env:TEST_ENV="dev"     → 本地 Flask Mock（默认，零外网）
  $env:TEST_ENV="real"    → 本地 FastAPI 真实后端（电商：JWT+SQLite，全维度测试）
  $env:TEST_ENV="test"    → jsonplaceholder.typicode.com（公开免费 API）
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
    """环境过滤：把用例分发到对应环境，不跑的跳过。

    三个被测系统、三套互斥 marker：
    - mock_only → 仅 dev（Flask Mock）
    - real_env  → 仅 test/staging（jsonplaceholder 等公开 API）
    - backend   → 仅 real（本地 FastAPI 后端）

    过滤规则：
    - dev：跳过 real_env 和 backend（只跑 Flask Mock）
    - real：跳过 mock_only 和 real_env（只跑 FastAPI 后端；test_real_env 用例改 test 跑）
    - test/staging：跳过 mock_only 和 backend（只跑 jsonplaceholder）
    """
    settings = get_settings()

    def skip_if_marked(item, mark, reason):
        if mark in item.keywords:
            item.add_marker(pytest.mark.skip(reason=reason))

    env = settings.env
    if env == "dev":
        for item in items:
            # dev 只跑 mock_only；跳过 real_env、backend
            skip_if_marked(item, "real_env", "dev 环境不跑公开环境用例（切 test 运行）")
            skip_if_marked(item, "backend", "dev 环境不跑后端用例（切 real 运行）")
    elif env == "real":
        for item in items:
            # real 只跑 backend；跳过 mock_only、real_env
            skip_if_marked(item, "mock_only", "real 环境不跑 Mock（切 dev 运行）")
            skip_if_marked(item, "real_env", "real 环境不跑 jsonplaceholder（切 test 运行）")
    else:  # test / staging
        for item in items:
            # test/staging 只跑 real_env；跳过 mock_only、backend
            skip_if_marked(item, "mock_only", "非 dev 不跑 Mock（切 dev 运行）")
            skip_if_marked(item, "backend", "test/staging 不跑后端（切 real 运行）")


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def is_mock_env(settings: Settings) -> bool:
    return settings.env == "dev"


@pytest.fixture(scope="session")
def is_backend_env(settings: Settings) -> bool:
    """real 环境专指「本地 FastAPI 后端」。"""
    return settings.env == "real"


# ── Mock 层（仅 dev 环境） ──
@pytest.fixture(scope="session")
def mock_db(is_mock_env: bool) -> MockDB | None:
    if not is_mock_env:
        return None
    return MockDB()


@pytest.fixture(scope="session")
def mock_server(is_mock_env: bool, settings: Settings, mock_db: MockDB | None) -> MockServer | None:
    if not is_mock_env:
        logger.info("TEST_ENV=%s → 不启动 Mock", settings.env)
        return None
    server = MockServer(host=settings.mock_host, port=None, db=mock_db, login_rate_limit=0)
    return server.start()


# ── 真实后端层（仅 real 环境） ──
@pytest.fixture(scope="session")
def backend_server(is_backend_env: bool, settings: Settings):
    """real 环境用子进程起 FastAPI 后端；测完优雅关闭。"""
    if not is_backend_env:
        logger.info("TEST_ENV=%s → 不启动 FastAPI 后端", settings.env)
        yield None
        return

    from core.backend_server import BackendServer

    srv = BackendServer(host=settings.mock_host, port=None)
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


# ── URL 层 ──
@pytest.fixture(scope="session")
def base_url(mock_server: MockServer | None, backend_server, settings: Settings) -> str:
    """dev→Mock, real→后端, 其余→settings.base_url。"""
    if mock_server is not None:
        return mock_server.base_url
    if backend_server is not None:
        return backend_server.base_url
    return settings.base_url


@pytest.fixture(scope="session")
def auth_url(mock_server: MockServer | None, backend_server, settings: Settings) -> str:
    if mock_server is not None:
        return mock_server.auth_url
    if backend_server is not None:
        return backend_server.auth_url
    return settings.auth_url


# ── Token（dev/real 都走登录；test/staging 按需） ──
@pytest.fixture(scope="session")
def token_manager(is_mock_env: bool, is_backend_env: bool, auth_url: str,
                  settings: Settings) -> TokenManager | None:
    if not is_mock_env and not is_backend_env:
        # test（jsonplaceholder）无鉴权
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
    """带 Token 的客户端（鉴权用例用）。"""
    client = HttpClient(
        base_url=base_url,
        token_manager=token_manager,
        timeout=settings.timeout,
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def raw_client(base_url: str, settings: Settings) -> HttpClient:
    """不带 Token 的裸客户端（登录/公开接口/负向用例用）。"""
    client = HttpClient(
        base_url=base_url,
        token_manager=None,
        timeout=settings.timeout,
    )
    yield client
    client.close()


# ── 后端环境的 DB 白盒断言助手（real 环境） ──
@pytest.fixture(scope="session")
def db_helper(is_backend_env: bool, backend_server):
    """real 环境才返回 DBHelper；其余环境为 None。"""
    if not is_backend_env:
        return None
    from utils.db_helper import DBHelper
    return DBHelper()


# ── 接口封装层（PO 模式）：按需注入 ──
@pytest.fixture(scope="session")
def auth_api(raw_client: HttpClient):
    from apis import AuthAPI
    return AuthAPI(raw_client)


@pytest.fixture(scope="session")
def product_api(api_client: HttpClient):
    from apis import ProductAPI
    return ProductAPI(api_client)


@pytest.fixture(scope="session")
def order_api(api_client: HttpClient):
    from apis import OrderAPI
    return OrderAPI(api_client)


@pytest.fixture(scope="session")
def payment_api(api_client: HttpClient):
    from apis import PaymentAPI
    return PaymentAPI(api_client)


# ── 兼容旧 fixture 名 ──
@pytest.fixture(scope="session")
def config(settings: Settings) -> Settings:
    return settings


@pytest.fixture(scope="session")
def base_request(api_client: HttpClient) -> HttpClient:
    return api_client
