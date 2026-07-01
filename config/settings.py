import os


class BaseConfig:
    APP_NAME = "api-test-platform"
    TIME_OUT = (5, 15)


class DevConfig(BaseConfig):
    BASE_URL = "http://localhost:8080"
    AUTH_URL = "http://localhost:8080/auth/login"
    USERNAME = "admin"
    PASSWORD = "admin123"


class TestConfig(BaseConfig):
    BASE_URL = "http://test.example.com:8080"
    AUTH_URL = "http://test.example.com:8080/auth/login"
    USERNAME = "test_user"
    PASSWORD = "test_pass"


class StagingConfig(BaseConfig):
    BASE_URL = "https://staging.example.com"
    AUTH_URL = "https://staging.example.com/auth/login"
    USERNAME = "staging_user"
    PASSWORD = "staging_pass"


ENV_MAP = {
    "dev": DevConfig,
    "test": TestConfig,
    "staging": StagingConfig,
}


def get_config(env: str = None):
    env = env or os.getenv("TEST_ENV", "dev")
    config_class = ENV_MAP.get(env)
    if not config_class:
        raise ValueError(f"未知环境: {env}，可选: {list(ENV_MAP.keys())}")
    return config_class()