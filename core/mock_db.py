"""Mock 内存数据库：模拟订单落库 + 支付状态变更。

设计意图：
- 演示「接口测试中为何要校验数据库」——HTTP 200 不代表数据真的落库
- 面试场景：Mock 里没有 DB 时也能讲清「如果是真实环境会怎么做」
- 操作：登录→下单→查库验证→支付→查库验证状态变更

用法:
    from core.mock_db import MockDB
    db = MockDB()
    order = db.create_order("ORD_001", amount=99.99)
    db.set_payment_status("ORD_001", "paid")
    assert db.get_order("ORD_001")["status"] == "paid"
"""
from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrderRecord:
    order_id: str
    amount: float
    status: str  # pending | paid | cancelled


class MockDB:
    """线程安全的内存数据库（pytest-xdist 并行时每个 worker 独立）。"""

    def __init__(self) -> None:
        self._orders: dict[str, OrderRecord] = {}
        self._users: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ── 预置种子数据（session 启动时调用一次） ──
    def seed_orders(self) -> None:
        with self._lock:
            self._orders.clear()
            self._orders["ORD_DB_00001"] = OrderRecord("ORD_DB_00001", 99.99, "paid")
            self._orders["ORD_DB_00002"] = OrderRecord("ORD_DB_00002", 199.00, "pending")
            self._orders["ORD_DB_00003"] = OrderRecord("ORD_DB_00003", 59.90, "cancelled")

    # ── 订单操作 ──
    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._orders.get(order_id)
            if record is None:
                return None
            return {
                "order_id": record.order_id,
                "amount": record.amount,
                "status": record.status,
            }

    def create_order(self, order_id: str, amount: float, status: str = "pending") -> dict[str, Any]:
        with self._lock:
            record = OrderRecord(order_id=order_id, amount=amount, status=status)
            self._orders[order_id] = record
            return {
                "order_id": record.order_id,
                "amount": record.amount,
                "status": record.status,
            }

    def update_payment(self, order_id: str, status: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._orders.get(order_id)
            if record is None:
                return None
            record.status = status
            return {
                "order_id": record.order_id,
                "amount": record.amount,
                "status": record.status,
            }

    def list_orders(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"order_id": r.order_id, "amount": r.amount, "status": r.status}
                for r in self._orders.values()
            ]

    def order_count(self) -> int:
        with self._lock:
            return len(self._orders)