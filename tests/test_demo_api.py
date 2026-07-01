"""示例测试：使用 httpbin.org 作为公开 API 演示"""
import pytest
import requests


class TestHttpBin:
    """以 httpbin.org 为练习目标的演示用例"""

    BASE_URL = "https://httpbin.org"

    def test_get_request(self):
        """演示 GET 请求"""
        response = requests.get(f"{self.BASE_URL}/get", params={"foo": "bar"})
        assert response.status_code == 200
        data = response.json()
        assert data["args"]["foo"] == "bar"

    def test_post_json(self):
        """演示 POST JSON 请求"""
        payload = {"name": "test", "value": 123}
        response = requests.post(f"{self.BASE_URL}/post", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["json"]["name"] == "test"

    @pytest.mark.parametrize("status_code", [200, 301, 404, 500])
    def test_status_codes(self, status_code):
        """参数化演示：测试多个 HTTP 状态码"""
        response = requests.get(f"{self.BASE_URL}/status/{status_code}")
        assert response.status_code == status_code

    def test_delayed_response(self):
        """演示超时处理：模拟延迟响应"""
        response = requests.get(f"{self.BASE_URL}/delay/2", timeout=5)
        assert response.status_code == 200

    def test_headers_inspection(self):
        """演示请求头/响应头分析"""
        response = requests.get(
            f"{self.BASE_URL}/headers",
            headers={"X-Custom-Header": "test-value"}
        )
        data = response.json()
        assert data["headers"]["X-Custom-Header"] == "test-value"

    def test_mock_server_available(self):
        """验证 Mock 服务是否可访问（集成测试前哨）"""
        try:
            response = requests.post("http://localhost:5000/api/payment/status", timeout=2)
            assert response.status_code == 200
            print("✅ Mock 服务可用")
        except requests.ConnectionError:
            pytest.skip("Mock 服务未启动，跳过该用例")