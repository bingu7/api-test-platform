"""订单路由：下单 / 查本人订单 / 取消订单。

IDOR（越权）防护——接口安全测试重点：
- 查/取消订单时校验 order.user_id == current_user.id，否则 403
- 这样普通用户不能通过改 order_id 访问/操作别人的订单
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.database import get_db
from apps.backend.deps import get_current_user
from apps.backend.models import Order, OrderStatus, Product, User
from apps.backend.schemas import OrderCreate, OrderOut

router = APIRouter(prefix="/api/orders", tags=["订单"])


async def _load_owned_order(db: AsyncSession, order_id: str, user: User) -> Order:
    """加载订单并校验归属。不存在 → 404；不归本人 → 403（IDOR 防护核心）。"""
    order = (await db.execute(select(Order).where(Order.order_id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该订单")
    return order


@router.get("", response_model=list[OrderOut])
async def list_my_orders(db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)) -> list[Order]:
    """列出当前用户的订单（只看到自己的）。"""
    rows = (await db.execute(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    )).scalars().all()
    return list(rows)


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)) -> Order:
    """下单。订单号重复 → 400；金额 ≤ 0 → 422（Pydantic 已拦）；商品不存在 → 422。"""
    dupe = (await db.execute(select(Order).where(Order.order_id == payload.order_id))).scalar_one_or_none()
    if dupe is not None:
        raise HTTPException(status_code=400, detail="订单号已存在")

    # 引用性校验：前端传了 product_id 就必须真实存在，否则收下的是「买不存在商品」的脏单
    if payload.product_id is not None:
        product = (await db.execute(select(Product).where(Product.id == payload.product_id))).scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=422, detail="商品不存在")

    order = Order(
        order_id=payload.order_id,
        user_id=user.id,
        product_id=payload.product_id,
        amount=payload.amount,
        status=OrderStatus.pending.value,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)) -> Order:
    """查订单详情（仅本人）。不存在 → 404；他人订单 → 403。"""
    return await _load_owned_order(db, order_id, user)


@router.put("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(order_id: str, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)) -> Order:
    """取消订单。已支付 → 400（不能直接取消已付单）；他人订单 → 403。"""
    order = await _load_owned_order(db, order_id, user)
    if order.status == OrderStatus.paid.value:
        raise HTTPException(status_code=400, detail="已支付的订单不能取消，请申请退款")
    order.status = OrderStatus.cancelled.value
    await db.commit()
    await db.refresh(order)
    return order
