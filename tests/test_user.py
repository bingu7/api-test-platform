import pytest
from core.base_request import BaseRequest
from core.mock_server import start_mock_server, stop_mock_server
from core.token_manager import TokenManager

@pytest.fixture(scope="module", autouse=True)
def mock_server():
    server, port = start_mock_server()
    yield port
    stop_mock_server(server)

@pytest.fixture(scope="module")
def br(mock_server):
    tm = TokenManager(
        auth_url=f"http://localhost:{mock_server}/api/login",
        credentials={"username": "admin", "password": "123456"},
    )
    return BaseRequest(base_url=f"http://localhost:{mock_server}", token_manager=tm)

def test_user_profile(br):
    response = br.request("GET", "/api/user/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["username"] == "admin"
    assert data["data"]["role"] == "tester"