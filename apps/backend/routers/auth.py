"""鉴权路由：注册 / 登录 / 取当前用户。

对应接口测试里的「正/负向」黄金样本：
- 注册：成功 201、重复用户名/邮箱 400、字段非法 422
- 登录：成功 200 返回 JWT、密码错 401
- /me：带 token 200、无 token 401
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.auth import hash_password, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from apps.backend.database import get_db
from apps.backend.deps import get_current_user
from apps.backend.models import User, UserRole
from apps.backend.schemas import UserCreate, UserLogin, UserOut, TokenOut

router = APIRouter(prefix="/api/auth", tags=["鉴权"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    """注册新用户。用户名/邮箱重复 → 400。"""
    # 查重——SQLAlchemy 参数化查询，天然防 SQL 注入
    existing = (await db.execute(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    )).scalar_one_or_none()
    if existing is not None:
        if existing.username == payload.username:
            raise HTTPException(status_code=400, detail="用户名已存在")
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    user = User(
        username=payload.username,
        email=str(payload.email),
        hashed_password=hash_password(payload.password),
        role=UserRole.user.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenOut:
    """登录：账号密码正确返回 JWT，否则 401。

    统一返回「用户名或密码错误」，不泄露用户是否存在（消除用户枚举漏洞）。
    """
    user = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role})
    return TokenOut(access_token=token, expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    """取当前登录用户信息。需要 Bearer token。"""
    return current_user
