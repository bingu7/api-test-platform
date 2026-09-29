"""数据库白盒断言助手。

作用（学习重点）：
- HTTP 返回 200 不代表数据真的落库 / 状态真的变了。
- 这个助手直连 SQLite 文件，绕过后端 ORM，做「地面真相」断言。
- 接口测试里「双校验」= API 返回 + DB 实际状态，缺一不可。

同步 sqlite3（aiosqlite 在测试里反而复杂；这里直连文件做只读查询就够）。
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from utils.paths import PROJECT_ROOT

# 后端 SQLite 文件：与 apps/backend/database.py 一致，同样尊重 BACKEND_DB_PATH 覆盖，
# 否则自定义 DB 路径时白盒断言会打到错误文件上。
DEFAULT_DB_PATH = Path(os.getenv("BACKEND_DB_PATH", PROJECT_ROOT / "apps" / "backend" / "dev.db"))


class DBHelper:
    """直连 SQLite 做白盒查询。只读用法为主，改写仅用于测试后清理。"""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}（后端是否已启动？）")

    def _connect(self) -> sqlite3.Connection:
        # row_factory 让查询结果可按列名取：row["username"]
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ── 用户 ──
    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def count_users(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    # ── 商品 ──
    def get_product(self, product_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
        return dict(row) if row else None

    def count_products(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    # ── 订单 ──
    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE order_id = ?", (order_id,)
            ).fetchone()
        return dict(row) if row else None

    def count_orders(self, user_id: int | None = None) -> int:
        with self._connect() as conn:
            if user_id is None:
                return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            return conn.execute(
                "SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)
            ).fetchone()[0]

    # ── 支付 ──
    def get_latest_payment(self, order_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM payments WHERE order_id = ? ORDER BY created_at DESC LIMIT 1",
                (order_id,),
            ).fetchone()
        return dict(row) if row else None

    def count_payments(self, order_id: str | None = None) -> int:
        with self._connect() as conn:
            if order_id is None:
                return conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
            return conn.execute(
                "SELECT COUNT(*) FROM payments WHERE order_id = ?", (order_id,)
            ).fetchone()[0]

    def get_payment_by_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM payments WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        return dict(row) if row else None

    # ── 断言式便捷方法（带 self.assert_ 前缀的语义化封装，供测试直接用） ──
    def assert_order_status(self, order_id: str, expected_status: str) -> None:
        order = self.get_order(order_id)
        assert order is not None, f"订单不存在: {order_id}"
        assert order["status"] == expected_status, (
            f"订单 {order_id} 状态不符: 期望 {expected_status}, 实际 {order['status']}"
        )

    def assert_payment_status(self, order_id: str, expected_status: str) -> None:
        payment = self.get_latest_payment(order_id)
        assert payment is not None, f"未找到订单 {order_id} 的支付记录"
        assert payment["status"] == expected_status, (
            f"订单 {order_id} 支付状态不符: 期望 {expected_status}, 实际 {payment['status']}"
        )
