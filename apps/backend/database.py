"""数据库层：异步 SQLAlchemy + SQLite。

设计要点（学习时关注）：
1. 用 aiosqlite 驱动，所有 DB 操作都是 async，配合 FastAPI 的 async 路由。
2. SQLite 文件路径支持环境变量覆盖，默认放在 apps/backend/dev.db。
3. 启动时自动建表（Base.metadata.create_all）——演示用，真实项目用 Alembic 做迁移。
4. 每次 BackendServer 启动会清空 DB 文件，保证测试隔离（见 core/backend_server.py）。
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# 后端包根目录：apps/backend/
BACKEND_DIR = Path(__file__).resolve().parent

# SQLite 文件路径：可用环境变量覆盖；默认 dev.db
DB_PATH = Path(os.getenv("BACKEND_DB_PATH", BACKEND_DIR / "dev.db"))

# SQLAlchemy 异步引擎。check_same_thread=False 是 aiosqlite 必需的。
_async_engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)

# 异步会话工厂。expire_on_commit=False：提交后仍能访问对象属性，避免 async 下常见的 lazy-load 报错。
AsyncSessionLocal = async_sessionmaker(
    bind=_async_engine,
    expire_on_commit=False,
)

# 连接 URL（给 BackendServer 做就绪探测 / 排障用）
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


async def init_db() -> None:
    """建表。启动 / 测试 fixture 调用一次即可。"""
    # 必须先 import models，让 ORM 类注册到 Base.metadata
    from apps.backend import models  # noqa: F401

    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI 依赖：为每个请求提供一个独立的异步会话，请求结束自动关闭。"""
    async with AsyncSessionLocal() as session:
        yield session
