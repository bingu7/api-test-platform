"""Pydantic 请求/响应模型（数据校验 + 序列化）。

学习重点：
- Pydantic 让 FastAPI 自动做「字段必填 / 类型 / 邮箱格式 / 金额>0」校验，
  不合规则返回 422——这是真实 API 里 422 的来源（接口测试常忽略，面试加分点）。
- 响应模型 (response_model) 决定返回哪些字段，天然剔除 hashed_password 等敏感字段。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── 认证 ──
class UserCreate(BaseModel):
    """注册请求体。"""
    username: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def username_no_spaces(cls, v: str) -> str:
        if " " in v:
            raise ValueError("用户名不能包含空格")
        return v


class UserLogin(BaseModel):
    """登录请求体。"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    """用户对外响应。无 hashed_password。"""
    id: int
    username: str
    email: str
    role: str
    created_at: datetime | None = None


class TokenOut(BaseModel):
    """登录成功响应。"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒


class LoginFailOut(BaseModel):
    """登录失败响应（FastAPI HTTPException 默认形状）。"""
    detail: str


# ── 商品 ──
class ProductCreate(BaseModel):
    """新建商品。管理员用。"""
    name: str = Field(..., min_length=1, max_length=128)
    price: float = Field(..., gt=0, description="价格必须大于 0")
    stock: int = Field(0, ge=0, description="库存不能为负")
    description: str = ""


class ProductUpdate(BaseModel):
    """更新商品。所有字段可选（PATCH 语义，但用 PUT 也能接受部分更新）。"""
    name: str | None = None
    price: float | None = Field(None, gt=0)
    stock: int | None = Field(None, ge=0)
    description: str | None = None


class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    stock: int
    description: str


# ── 订单 ──
class OrderCreate(BaseModel):
    """下单请求。"""
    order_id: str = Field(..., min_length=1, max_length=32, description="业务订单号")
    product_id: int | None = None
    amount: float = Field(..., gt=0, description="金额必须大于 0")


class OrderOut(BaseModel):
    id: int
    order_id: str
    user_id: int
    product_id: int | None
    amount: float
    status: str
    created_at: datetime | None = None


# ── 支付 ──
class PaymentCreate(BaseModel):
    """支付请求。idempotency_key 保证幂等。"""
    order_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1, max_length=64)


class PaymentRefund(BaseModel):
    """退款请求。"""
    order_id: str = Field(..., min_length=1)


class PaymentOut(BaseModel):
    id: int
    order_id: str
    amount: float
    status: str
    idempotency_key: str
    created_at: datetime | None = None
