import threading

from flask import Flask, jsonify, request
from werkzeug.serving import make_server


def start_mock_server(port=5000):
    """启动 Mock 服务，返回 (线程对象, 端口号)"""
    app = Flask(__name__)

    @app.route("/api/payment/status", methods=["POST"])
    def mock_payment():
        return jsonify({
            "code": 0,
            "message": "支付成功",
            "data": {"order_id": "MOCK_20240001", "amount": 99.99, "status": "paid"},
        })

    @app.route("/api/payment/timeout", methods=["POST"])
    def mock_payment_timeout():
        return jsonify({"code": -1, "message": "请求超时"}), 504

    @app.route("/api/login", methods=["POST"])
    def mock_login():
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if username == "admin" and password == "123456":
            return jsonify({"code": 0, "message": "登录成功", "access_token": "MOCK_TOKEN", "expires_in": 3600})
        elif username == "admin" and password != "123456":
            return jsonify({"code": -1, "message": "密码错误"}), 401
        else:
            return jsonify({"code": -1, "message": "用户未找到"}), 404

    server = make_server("127.0.0.1", port, app)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    server.thread = server_thread
    return server, port


def stop_mock_server(server):
    """停止 Mock 服务（线程会随着测试结束自动停止）"""
    server.shutdown()
    server.thread.join(timeout=2)


if __name__ == "__main__":
    server, _ = start_mock_server()
    try:
        server.thread.join()
    except KeyboardInterrupt:
        stop_mock_server(server)
