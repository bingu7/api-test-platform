"""数据驱动测试：使用 Excel + Mock 服务，测试登录接口"""
import pytest
from core.base_request import BaseRequest
from core.token_manager import TokenManager
from core.mock_server import start_mock_server, stop_mock_server
from utils.excel_reader import read_test_cases

# 读取 Excel 数据（模块级别，只读一次）
test_data = read_test_cases("data/test_cases.xlsx")


@pytest.fixture(scope="module", autouse=True)
def mock_server():
    """启动 Mock 服务"""
    server_thread, port = start_mock_server()
    yield port
    stop_mock_server(server_thread)


class TestLogin:

    @pytest.fixture(scope="class")
    def br(self):
        """创建一个指向 Mock 服务的 BaseRequest"""
        tm = TokenManager(
            auth_url="http://localhost:5000/api/login",
            credentials={"username": "admin", "password": "123456"}
        )
        return BaseRequest(base_url="http://localhost:5000", token_manager=tm)

    @pytest.mark.parametrize("case", test_data, ids=lambda c: c["name"])
    def test_login(self, case, br):
        """数据驱动：1 个方法跑所有登录场景"""
        response = br.request(
            method=case["method"],
            endpoint=case["endpoint"],
            json=case["body"]
        )
        assert response.status_code == case["expected_status"], (
            f"用例 '{case['name']}' 失败：期望状态码 {case['expected_status']}，实际 {response.status_code}"
        )