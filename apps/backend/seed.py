"""初始化演示数据：2 个用户 + 3 个商品 + 1 个种子订单。

BackendServer 启动后由 main.py 的 lifespan 调用一次，让接口测试有可预期的初始状态。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.auth import hash_password
from apps.backend.database import AsyncSessionLocal
from apps.backend.models import User, UserRole, Product, Order, OrderStatus


async def seed() -> None:
    """插入演示数据（如已存在则跳过，保证可重复执行）。"""
    async with AsyncSessionLocal() as db:
        # admin
        admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if admin is None:
            admin = User(
                username="admin",
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                role=UserRole.admin.value,
            )
            db.add(admin)
            await db.flush()  # 拿到 admin.id

        # tester（普通用户）
        tester = (await db.execute(select(User).where(User.username == "tester"))).scalar_one_or_none()
        if tester is None:
            tester = User(
                username="tester",
                email="tester@example.com",
                hashed_password=hash_password("tester123"),
                role=UserRole.user.value,
            )
            db.add(tester)
            await db.flush()

        # 3 个商品
        if (await db.execute(select(Product).where(Product.name == "商品A"))).scalar_one_or_none() is None:
            db.add_all([
                Product(name="商品A", price=9.9, stock=100, description="测试商品A"),
                Product(name="商品B", price=19.9, stock=50, description="测试商品B"),
                Product(name="商品C", price=99.0, stock=10, description="测试商品C"),
            ])

        # 1 个种子订单（tester 的，pending）——链路测试用
        if (await db.execute(select(Order).where(Order.order_id == "SEED_ORD_001"))).scalar_one_or_none() is None:
            db.add(Order(
                order_id="SEED_ORD_001",
                user_id=tester.id,
                product_id=None,
                amount=199.0,
                status=OrderStatus.pending.value,
            ))

        await db.commit()


async def reset_and_seed() -> None:
    """清表 + 建表 + 灌数据。BackendServer 启动时调用，保证测试隔离。"""
    from apps.backend.database import init_db
    await init_db()
    await seed()
