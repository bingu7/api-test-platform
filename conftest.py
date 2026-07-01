import pytest
from core.base_request import BaseRequest
from core.token_manager import TokenManager
from config.settings import get_config


@pytest.fixture(scope="session")
def config():
    return get_config()


@pytest.fixture(scope="session")
def base_request(config):
    tm = TokenManager(
        auth_url=config.AUTH_URL,
        credentials={"user": config.USERNAME, "password": config.PASSWORD},
    )
    br = BaseRequest(base_url=config.BASE_URL, token_manager=tm)
    return br