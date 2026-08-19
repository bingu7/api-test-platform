"""支付路由：支付（幂等）/ 退款 / 查支付状态。

幂等性（idempotency）——接口测试的高阶点：
- 同一 idempotency_key 第二次请求不会重复扣款，直接返回首次结果
- 一个 order 只能成功支付一次（状态机：pending→paid）
- 已退款不能再退
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.database import get_db
from apps.backend.deps import get_current_user
from apps.backend.models import Order, OrderStatus, Payment, PaymentStatus, User
from apps.backend.schemas import PaymentCreate, PaymentRefund, PaymentOut

router = APIRouter(prefix="/api/payment", tags=["支付"])


async def _load_owned_order(db: AsyncSession, order_id: str, user: User) -> Order:
    """加载订单并校验归属。不存在 → 404；不归本人 → 403。"""
    order = (await db.execute(select(Order).where(Order.order_id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该订单")
    return order


@router.post("/pay", response_model=PaymentOut)
async def pay(payload: PaymentCreate, db: AsyncSession = Depends(get_db),
              user: User = Depends(get_current_user)) -> Payment:
    """支付订单。"""
    order = await _load_owned_order(db, payload.order_id, user)

    # 幂等：同一 idempotency_key 重复请求 → 返回已存在记录，不重复扣款
    existing = (await db.execute(
        select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
    )).scalar_one_or_none()
    if existing is not None:
        # 幂等保护：即使 order 已发生状态变更，也只回放首次支付结果
        return existing

    if order.status == OrderStatus.paid.value:
        # 换了 idempotency_key 但订单已付 → 不允许重复支付
        raise HTTPException(status_code=400, detail="订单已支付")
    if order.status == OrderStatus.cancelled.value:
        raise HTTPException(status_code=400, detail="订单已取消，无法支付")

    payment = Payment(
        order_id=order.order_id,
        amount=order.amount,
        status=PaymentStatus.success.value,
        idempotency_key=payload.idempotency_key,
    )
    db.add(payment)
    order.status = OrderStatus.paid.value  # 推动订单状态机
    await db.commit()
    await db.refresh(payment)
    return payment


@router.post("/refund", response_model=PaymentOut)
async def refund(payload: PaymentRefund, db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)) -> Payment:
    """退款。需要订单已支付，否则 → 400。"""
    order = await _load_owned_order(db, payload.order_id, user)
    if order.status != OrderStatus.paid.value:
        raise HTTPException(status_code=400, detail="订单未支付，无法退款")

    # 找到该订单的成功支付记录，标记为 refunded；订单回到 pending（可再次支付/取消）
    payment = (await db.execute(
        select(Payment).where(Payment.order_id == order.order_id,
                              Payment.status == PaymentStatus.success.value)
    )).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="未找到支付记录")

    payment.status = PaymentStatus.refunded.value
    order.status = OrderStatus.pending.value
    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("/status/{order_id}", response_model=PaymentOut)
async def payment_status(order_id: str, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)) -> Payment:
    """查某订单的支付状态。"""
    await _load_owned_order(db, order_id, user)  # 校验归属
    payment = (await db.execute(
        select(Payment).where(Payment.order_id == order_id)
        .order_by(Payment.created_at.desc())
    )).scalars().first()
    if payment is None:
        raise HTTPException(status_code=404, detail="未找到支付记录")
    return payment
