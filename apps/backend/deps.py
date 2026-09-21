"""FastAPI 依赖注入：数据库会话、当前用户、权限校验。

这是「鉴权」的实现点——接口测试的核心校验对象：
- 无/失效 token → 401
- 有 token 但权限不足 → 403
- 把 current_user 注入路由，路由据此判断是否为本人订单（IDOR 防护）
"""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.auth import decode_access_token
from apps.backend.database import get_db
from apps.backend.models import User, UserRole

# Bearer token 提取器：FastAPI 会自动从 Authorization 头解析 Bearer <token>
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 解出 User；无 token / 失效 token / 用户不存在都返回 401。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供有效的认证信息",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 已过期")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 无效")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 缺少用户标识")
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        # 签名合法但 payload 畸形（user_id 非数字）→ 视为非法 token，绝不能抛 500
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 用户标识非法")

    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """需要管理员权限。普通用户访问 admin 接口 → 403。"""
    if user.role != UserRole.admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选鉴权：带了合法 token 就解出用户，没有就返回 None（用于公开但可个性化的接口）。"""
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        return None
    user_id = payload.get("user_id")
    if not user_id:
        return None
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
