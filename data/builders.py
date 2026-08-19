"""数据构造器（Builder 模式）。

为什么要有 builders（学习重点）：
- 测试里直接写字典 `{"username":"admin","password":"123456"}` 会把数据硬编码，改一处要改多处。
- Builder 让你链式造数据，只写关心的字段，其余用默认：
    UserData().with_username("jack").build()
  默认字段满足合法约束（如 password 至少 6 位），不用每次想合法值。
- 负向测试时显式覆写：UserData().with_password("123").build()  → 短密码（应 422）。
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field, replace
from typing import Any


def _random_suffix() -> str:
    return secrets.token_hex(4)


@dataclass(frozen=True)
class UserData:
    """注册/登录数据。默认是一组合法凭证。"""
    username: str = field(default_factory=lambda: f"user_{_random_suffix()}")
    email: str = ""
    password: str = "Passw0rd!"

    def __post_init__(self):
        # email 没传就用 username@example.com 凑一个合法邮箱
        if not self.email:
            object.__setattr__(self, "email", f"{self.username}@example.com")

    def build(self) -> dict[str, Any]:
        """转成可直接发给注册/登录接口的字典。"""
        return {"username": self.username, "email": self.email, "password": self.password}

    # ── 链式 with_* ──（返回新对象，dataclass 不可变）
    def with_username(self, v: str) -> "UserData":
        return replace(self, username=v, email=f"{v}@example.com" if "@" not in self.email or self.email == f"{self.username}@example.com" else self.email)

    def with_email(self, v: str) -> "UserData":
        return replace(self, email=v)

    def with_password(self, v: str) -> "UserData":
        return replace(self, password=v)


@dataclass(frozen=True)
class ProductData:
    """商品数据。默认合法。"""
    name: str = field(default_factory=lambda: f"商品_{_random_suffix()}")
    price: float = 19.9
    stock: int = 100
    description: str = "测试商品"

    def build(self) -> dict[str, Any]:
        return {"name": self.name, "price": self.price, "stock": self.stock, "description": self.description}

    def with_name(self, v: str) -> "ProductData":
        return replace(self, name=v)

    def with_price(self, v: float) -> "ProductData":
        return replace(self, price=v)

    def with_stock(self, v: int) -> "ProductData":
        return replace(self, stock=v)


@dataclass(frozen=True)
class OrderData:
    """订单数据。默认合法。order_id 默认随机，避免撞单。"""
    order_id: str = field(default_factory=lambda: f"ORD_{_random_suffix()}{secrets.token_hex(4)}")
    amount: float = 99.0
    product_id: int | None = None

    def build(self) -> dict[str, Any]:
        body: dict[str, Any] = {"order_id": self.order_id, "amount": self.amount}
        if self.product_id is not None:
            body["product_id"] = self.product_id
        return body

    def with_order_id(self, v: str) -> "OrderData":
        return replace(self, order_id=v)

    def with_amount(self, v: float) -> "OrderData":
        return replace(self, amount=v)

    def with_product_id(self, v: int) -> "OrderData":
        return replace(self, product_id=v)


@dataclass(frozen=True)
class PaymentData:
    """支付数据。idempotency_key 默认随机；要测幂等就显式传同一 key。"""
    idempotency_key: str = field(default_factory=lambda: f"idem_{secrets.token_hex(8)}")

    def build(self, order_id: str) -> dict[str, Any]:
        return {"order_id": order_id, "idempotency_key": self.idempotency_key}

    def with_key(self, v: str) -> "PaymentData":
        return replace(self, idempotency_key=v)
