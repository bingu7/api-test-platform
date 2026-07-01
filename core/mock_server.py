from flask import Flask, jsonify

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


def start_mock_server(port=5000):
    app.run(port=port, debug=False)


if __name__ == "__main__":
    start_mock_server()