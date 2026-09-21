"""支付接口封装。

对应后端 apps/backend/routers/payment.py：
- POST /api/payment/pay             支付（需登录；幂等 by idempotency_key）
- POST /api/payment/refund          退款（需登录；订单需已支付）
- GET  /api/payment/status/{id}     查支付状态（需登录，且仅本人）

幂等性测试重点：同一 idempotency_key 重复 pay，返回首次记录、不重复扣款。
"""
from __future__ import annotations

import secrets
from typing import Any

from requests import Response

from core.base_request import HttpClient


class PaymentAPI:
    """支付接口封装类。"""

    def __init__(self, client: HttpClient):
        self.client = client

    def pay(self, order_id: str, idempotency_key: str | None = None, **kw: Any) -> Response:
        """支付订单。idempotency_key 不传则自动生成一个（每次都新 → 默认不幂等）。"""
        key = idempotency_key or f"idem_{secrets.token_hex(8)}"
        return self.client.post(
            "/api/payment/pay",
            auth=True,
            json={"order_id": order_id, "idempotency_key": key},
            **kw,
        )

    def refund(self, order_id: str, **kw: Any) -> Response:
        """退款（订单需已支付，否则 400）。"""
        return self.client.post(
            "/api/payment/refund",
            auth=True,
            json={"order_id": order_id},
            **kw,
        )

    def status(self, order_id: str, **kw: Any) -> Response:
        """查某订单支付记录（最新一条）。无支付记录 → 404。"""
        return self.client.get(f"/api/payment/status/{order_id}", auth=True, **kw)
