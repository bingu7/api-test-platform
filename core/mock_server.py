"""本地 Mock API 服务。

- 绑定 127.0.0.1（Windows 避免 localhost 解析慢）
- port=0 时由系统分配空闲端口
- 启动后同步探测就绪，避免测试抢跑
- 接入 MockDB 内存存储，演示接口→数据库校验闭环
"""
from __future__ import annotations

import socket
import threading
import time
from typing import Any

import requests
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from core.mock_db import MockDB
from utils.logger import get_logger

logger = get_logger("mock")


def _pick_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        return sock.getsockname()[1]


def create_app(db: MockDB | None = None) -> Flask:
    app = Flask("api-test-mock")
    _db = db or MockDB()

    # ── 支付 ──
    @app.route("/api/payment/status", methods=["POST"])
    def mock_payment():
        body = request.get_json(silent=True) or {}
        order_id = body.get("order_id", "ORD_DB_00001")
        new_status = body.get("status", "paid")
        order = _db.update_payment(order_id, new_status)
        if order is None:
            return jsonify({"code": -1, "message": f"订单 {order_id} 不存在"}), 404
        return jsonify(
            {
                "code": 0,
                "message": "支付成功" if new_status == "paid" else "状态已更新",
                "data": order,
            }
        )

    @app.route("/api/payment/timeout", methods=["POST"])
    def mock_payment_timeout():
        return jsonify({"code": -1, "message": "请求超时"}), 504

    # ── 用户 ──
    @app.route("/api/user/profile", methods=["GET"])
    def mock_user_profile():
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

    # ── 订单 ──
    @app.route("/api/orders", methods=["GET"])
    def mock_orders():
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"code": -1, "message": "未授权"}), 401
        orders = _db.list_orders()
        return jsonify(
            {
                "code": 0,
                "message": "获取成功",
                "data": {"orders": orders},
            }
        )

    @app.route("/api/orders", methods=["POST"])
    def mock_create_order():
        body = request.get_json(silent=True) or {}
        order_id = body.get("order_id", f"ORD_{int(time.time() * 1000)}")
        amount = float(body.get("amount", 0))
        if amount <= 0:
            return jsonify({"code": -1, "message": "金额必须大于 0"}), 400
        order = _db.create_order(order_id, amount)
        return jsonify(
            {
                "code": 0,
                "message": "下单成功",
                "data": order,
            }
        ), 201

    @app.route("/api/orders/<order_id>/status", methods=["PUT"])
    def mock_update_order_status(order_id: str):
        body = request.get_json(silent=True) or {}
        status = body.get("status", "")
        order = _db.update_payment(order_id, status)
        if order is None:
            return jsonify({"code": -1, "message": f"订单 {order_id} 不存在"}), 404
        return jsonify(
            {
                "code": 0,
                "message": "状态已更新",
                "data": order,
            }
        )

    @app.route("/api/orders/<order_id>", methods=["GET"])
    def mock_get_order(order_id: str):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"code": -1, "message": "未授权"}), 401
        order = _db.get_order(order_id)
        if order is None:
            return jsonify({"code": -1, "message": f"订单 {order_id} 不存在"}), 404
        return jsonify(
            {
                "code": 0,
                "message": "获取成功",
                "data": order,
            }
        )

    # ── 边界场景 ──
    @app.route("/api/edge/empty-body", methods=["POST"])
    def mock_edge_empty_body():
        content_type = request.headers.get("Content-Type", "")
        if content_type and "application/json" not in content_type:
            return jsonify({"code": -1, "message": "Content-Type 必须为 application/json"}), 400
        body = request.get_json(silent=True)
        if not body:
            return jsonify({"code": -1, "message": "请求体不能为空"}), 422
        return jsonify({"code": 0, "message": "ok", "data": body})

    @app.route("/api/edge/missing-field", methods=["POST"])
    def mock_edge_missing_field():
        body = request.get_json(silent=True) or {}
        if "required_field" not in body:
            return jsonify({"code": -1, "message": "缺少必填字段 required_field"}), 422
        return jsonify({"code": 0, "message": "ok", "data": body})

    @app.route("/api/edge/large-payload", methods=["POST"])
    def mock_edge_large_payload():
        body = request.get_json(silent=True) or {}
        text = body.get("text", "")
        if len(text) > 10000:
            return jsonify({"code": -1, "message": "请求体过大"}), 413
        return jsonify({"code": 0, "message": "ok", "length": len(text)})

    @app.route("/api/edge/fatal-error", methods=["GET"])
    def mock_edge_server_error():
        raise RuntimeError("模拟服务端异常")

    # ── 登录 ──
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

    @app.errorhandler(500)
    def handle_server_error(_e: Any):
        return jsonify({"code": -1, "message": "服务器内部异常"}), 500

    return app


class MockServer:
    """可 start/stop 的 Mock 服务句柄。"""

    def __init__(self, host: str = "127.0.0.1", port: int | None = None, db: MockDB | None = None):
        self.host = host
        self.port = port if port is not None else _pick_free_port(host)
        self.db = db or MockDB()
        self._server = None
        self._thread: threading.Thread | None = None
        self.app = create_app(db=self.db)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def auth_url(self) -> str:
        return f"{self.base_url}/api/login"

    def start(self, ready_timeout: float = 5.0) -> "MockServer":
        self._server = make_server(self.host, self.port, self.app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.db.seed_orders()
        self._wait_ready(ready_timeout)
        logger.info("Mock 已启动: %s", self.base_url)
        return self

    def _wait_ready(self, timeout: float) -> None:
        deadline = time.time() + timeout
        probe = requests.Session()
        probe.trust_env = False
        while time.time() < deadline:
            try:
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
    return MockServer(host=host, port=port).start()


def stop_mock_server(server: MockServer) -> None:
    server.stop()