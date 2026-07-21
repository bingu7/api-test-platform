"""
本地 Mock API 服务。

- 绑定 127.0.0.1（Windows 避免 localhost 解析慢）
- port=0 时由系统分配空闲端口
- 启动后同步探测就绪，避免测试抢跑
"""
from __future__ import annotations

import socket
import threading
import time
from typing import Any

import requests
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from utils.logger import get_logger

logger = get_logger("mock")


def _pick_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def create_app() -> Flask:
    app = Flask("api-test-mock")

    @app.route("/api/payment/status", methods=["POST"])
    def mock_payment():
        return jsonify(
            {
                "code": 0,
                "message": "支付成功",
                "data": {
                    "order_id": "MOCK_20240001",
                    "amount": 99.99,
                    "status": "paid",
                },
            }
        )

    @app.route("/api/payment/timeout", methods=["POST"])
    def mock_payment_timeout():
        return jsonify({"code": -1, "message": "请求超时"}), 504

    @app.route("/api/user/profile", methods=["GET"])
    def mock_user_profile():
        # 简易鉴权演示：无 Bearer 返回 401（可选学习点）
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"code": -1, "message": "未授权"}), 401
        return jsonify(
            {
                "code": 0,
                "message": "获取成功",
                "data": {"username": "admin", "role": "tester"},
            }
        )

    @app.route("/api/orders", methods=["GET"])
    def mock_orders():
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"code": -1, "message": "未授权"}), 401
        return jsonify(
            {
                "code": 0,
                "message": "获取成功",
                "data": {
                    "orders": [
                        {
                            "order_id": "ORD_20240001",
                            "amount": 99.99,
                            "status": "paid",
                        },
                        {
                            "order_id": "ORD_20240002",
                            "amount": 199.00,
                            "status": "pending",
                        },
                        {
                            "order_id": "ORD_20240003",
                            "amount": 59.90,
                            "status": "cancelled",
                        },
                    ]
                },
            }
        )

    @app.route("/api/login", methods=["POST"])
    def mock_login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")

        if username == "admin" and password == "123456":
            return jsonify(
                {
                    "code": 0,
                    "message": "登录成功",
                    "access_token": "MOCK_TOKEN",
                    "expires_in": 3600,
                }
            )
        if username == "admin":
            return jsonify({"code": -1, "message": "密码错误"}), 401
        return jsonify({"code": -1, "message": "用户未找到"}), 404

    @app.errorhandler(404)
    def handle_not_found(_e: Any):
        return jsonify({"code": -1, "message": "接口不存在"}), 404

    return app


class MockServer:
    """可 start/stop 的 Mock 服务句柄。"""

    def __init__(self, host: str = "127.0.0.1", port: int | None = None):
        self.host = host
        self.port = port if port is not None else _pick_free_port(host)
        self._server = None
        self._thread: threading.Thread | None = None
        self.app = create_app()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def auth_url(self) -> str:
        return f"{self.base_url}/api/login"

    def start(self, ready_timeout: float = 5.0) -> "MockServer":
        self._server = make_server(self.host, self.port, self.app)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._wait_ready(ready_timeout)
        logger.info("Mock 已启动: %s", self.base_url)
        return self

    def _wait_ready(self, timeout: float) -> None:
        deadline = time.time() + timeout
        probe = requests.Session()
        probe.trust_env = False
        while time.time() < deadline:
            try:
                # 登录接口存在即可视为就绪（404 也说明 HTTP 栈已起来）
                probe.get(f"{self.base_url}/api/login", timeout=0.3)
                return
            except requests.RequestException:
                time.sleep(0.05)
        raise RuntimeError(f"Mock 服务在 {timeout}s 内未就绪: {self.base_url}")

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("Mock 已停止: %s", self.base_url)


def start_mock_server(host: str = "127.0.0.1", port: int | None = None) -> MockServer:
    """启动 Mock，返回 MockServer（含 base_url/port）。"""
    return MockServer(host=host, port=port).start()


def stop_mock_server(server: MockServer) -> None:
    server.stop()
