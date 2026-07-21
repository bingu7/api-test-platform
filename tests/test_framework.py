"""框架自测：路径、Excel、配置、Token 错误路径（不依赖业务接口语义）。"""
from __future__ import annotations

import pytest

from config.settings import get_settings
from core.token_manager import TokenError, TokenManager
from utils.excel_reader import filter_cases, read_test_cases
from utils.paths import DATA_DIR, PROJECT_ROOT, data_file


def test_project_paths():
    assert PROJECT_ROOT.name == "api-test-platform" or (PROJECT_ROOT / "pytest.ini").exists()
    assert DATA_DIR.is_dir()
    assert data_file("test_cases.xlsx").is_file()


def test_read_excel_default_path():
    cases = read_test_cases()
    assert len(cases) >= 5
    names = {c["name"] for c in cases}
    assert "正常登录" in names


def test_filter_login_cases():
    login = filter_cases(endpoints={"/api/login"})
    assert all(c["endpoint"] == "/api/login" for c in login)
    assert len(login) >= 3


def test_settings_unknown_env():
    with pytest.raises(ValueError, match="未知环境"):
        get_settings("no-such-env")


def test_settings_default_api_user_is_admin():
    """回归：勿读取 Windows 系统 USERNAME 导致账号变成当前系统用户。"""
    s = get_settings("dev")
    assert s.username == "admin"
    assert s.password == "123456"


def test_token_error_on_bad_password(mock_server, settings):
    tm = TokenManager(
        auth_url=mock_server.auth_url,
        credentials={"username": "admin", "password": "wrong"},
        timeout=settings.timeout,
    )
    with pytest.raises(TokenError, match="401"):
        tm.get_token()
