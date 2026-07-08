import pytest
import requests

from core.mock_server import start_mock_server, stop_mock_server


session = requests.Session()
session.trust_env = False


@pytest.fixture(scope="module")
def mock_server():
    server, port = start_mock_server()
    yield port
    stop_mock_server(server)


class TestMockApi:
    def test_payment_success(self, mock_server):
        response = session.post(f"http://localhost:{mock_server}/api/payment/status", timeout=2)

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "paid"

    def test_payment_timeout(self, mock_server):
        response = session.post(f"http://localhost:{mock_server}/api/payment/timeout", timeout=2)

        assert response.status_code == 504
        assert response.json()["message"] == "请求超时"

    @pytest.mark.parametrize(
        ("payload", "expected_status"),
        [
            ({"username": "admin", "password": "123456"}, 200),
            ({"username": "admin", "password": "wrong"}, 401),
            ({"username": "nobody", "password": "123"}, 404),
        ],
    )
    def test_login_status(self, mock_server, payload, expected_status):
        response = session.post(f"http://localhost:{mock_server}/api/login", json=payload, timeout=2)

        assert response.status_code == expected_status
