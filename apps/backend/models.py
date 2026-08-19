"""ORM 模型：User / Product / Order / Payment。

数据库里存什么、字段怎么设计——这是接口测试要校验的「真实落库」对象。
- Order.user_id 体现归属：越权测试（IDOR）就是验证普通用户改不了别人的订单。
- Order/Payment 的 status 用字符串枚举（pending/paid/cancelled/refunded），
  看真实业务里状态机长什么样。
"""
from __future__ import annotations

import enum
import time
from datetime import datetime

from sqlalchemy import ForeignKey, String, Integer, Float, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.database import Base


def _now() -> datetime:
    """记录创建/更新时间。统一用 datetime，避免 time.time() 的秒级精度。"""
    return datetime.utcnow()


class UserRole(str, enum.Enum):
    """用户角色：admin=管理员，user=普通用户。"""
    admin = "admin"
    user = "user"


class OrderStatus(str, enum.Enum):
    """订单状态：pending→paid，或 pending→cancelled。"""
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class PaymentStatus(str, enum.Enum):
    """支付记录状态：paid 之后可 refund。"""
    success = "success"
    refunded = "refunded"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # 哈希后的密码（绝不明存、绝不返回给前端——安全测试会校验这点）
    hashed_password: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default=UserRole.user.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")

    def to_dict(self) -> dict:
        """对外序列化——故意不带 hashed_password（安全测试会断言响应不含它）。"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    price: Mapped[float] = mapped_column(Float)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    orders: Mapped[list["Order"]] = relationship(back_populates="product")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "stock": self.stock,
            "description": self.description,
        }


class Order(Base):
    """订单：某用户买了某商品，金额、状态、归属人。"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # 业务订单号
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default=OrderStatus.pending.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped["User"] = relationship(back_populates="orders")
    product: Mapped["Product"] = relationship(back_populates="orders")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "product_id": self.product_id,
            "amount": self.amount,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Payment(Base):
    """支付记录：一条订单可有多次记录（原支付 + 退款），用 idempotency_key 幂等。"""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(32), ForeignKey("orders.order_id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default=PaymentStatus.success.value)
    # 幂等键：同一 key 重复支付只成功一次，避免重复扣款（接口幂等性练习用）
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    order: Mapped["Order"] = relationship(back_populates="payments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "amount": self.amount,
            "status": self.status,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
