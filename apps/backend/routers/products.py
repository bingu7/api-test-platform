"""商品路由：CRUD。

权限设计（接口测试重点校验对象）：
- GET 列表/详情：公开（任何人可看）
- POST 创建 / PUT 更新 / DELETE 删除：仅 admin（require_admin）→ 普通用户 403、无 token 401
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.database import get_db
from apps.backend.deps import require_admin, get_current_user
from apps.backend.models import Product, User
from apps.backend.schemas import ProductCreate, ProductUpdate, ProductOut

router = APIRouter(prefix="/api/products", tags=["商品"])


@router.get("", response_model=list[ProductOut])
async def list_products(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """商品列表（公开）。支持分页。"""
    rows = (await db.execute(select(Product).offset(skip).limit(limit))).scalars().all()
    return list(rows)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """商品详情。不存在 → 404。"""
    p = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return p


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, db: AsyncSession = Depends(get_db),
                         _: User = Depends(require_admin)) -> Product:
    """创建商品（仅 admin）。"""
    p = Product(name=payload.name, price=payload.price, stock=payload.stock, description=payload.description)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@router.put("/{product_id}", response_model=ProductOut)
async def update_product(product_id: int, payload: ProductUpdate, db: AsyncSession = Depends(get_db),
                         _: User = Depends(require_admin)) -> Product:
    """更新商品（仅 admin）。不存在 → 404。"""
    p = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return p


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db),
                         _: User = Depends(require_admin)):
    """删除商品（仅 admin）。不存在 → 404。"""
    p = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    await db.delete(p)
    await db.commit()
