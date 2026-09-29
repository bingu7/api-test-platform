"""订单接口封装。

对应后端 apps/backend/routers/orders.py：
- GET  /api/orders            我的订单列表（需登录）
- POST /api/orders            下单（需登录）
- GET  /api/orders/{order_id} 订单详情（需登录，且仅本人）
- PUT  /api/orders/{order_id}/cancel 取消订单（需登录，且仅本人）

IDOR 测试重点：用别人登录的 client 访问 /api/orders/{他单号} 应得 403。
"""
from __future__ import annotations

from typing import Any

from requests import Response

from core.base_request import HttpClient


class OrderAPI:
    """订单接口封装类。"""

    def __init__(self, client: HttpClient):
        self.client = client

    def list(self, **kw: Any) -> Response:
        """我的订单列表（auth=True，后端按 token 里的 user_id 过滤）。"""
        return self.client.get("/api/orders", auth=True, **kw)

    def create(self, order_id: str, amount: float, product_id: int | None = None,
               **kw: Any) -> Response:
        """下单（auth=True）。amount 必须 > 0，否则 422；order_id 重复则 400。"""
        body: dict[str, Any] = {"order_id": order_id, "amount": amount}
        if product_id is not None:
            body["product_id"] = product_id
        return self.client.post("/api/orders", auth=True, json=body, **kw)

    def get(self, order_id: str, **kw: Any) -> Response:
        """查订单详情（auth=True，仅本人可见；他人订单 → 403）。"""
        return self.client.get(f"/api/orders/{order_id}", auth=True, **kw)

    def cancel(self, order_id: str, **kw: Any) -> Response:
        """取消订单（auth=True，仅本人；已支付单 → 400）。"""
        return self.client.put(f"/api/orders/{order_id}/cancel", auth=True, **kw)
