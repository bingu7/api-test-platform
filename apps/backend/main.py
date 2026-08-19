"""FastAPI 应用入口 —— 后端被测系统。

启动方式（前台调试）：
    cd apps/backend && python -m uvicorn apps.backend.main:app --reload --port 8000
或（项目根）:
    python -m uvicorn apps.backend.main:app --port 8000

启动后：
    http://127.0.0.1:8000/docs      # Swagger UI（看接口契约）
    http://127.0.0.1:8000/openapi.json  # OpenAPI 规范（契约测试用）

测试由 core/backend_server.py 用子进程起这个 app，测完自动关。
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.backend.seed import reset_and_seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    """生命周期：启动时建表 + 灌演示数据，保证每次启动都是干净、可预期状态。"""
    await reset_and_seed()
    yield  # 应用运行期
    # 这里可以放优雅退出逻辑（连接池清理等），目前留空


def create_app() -> FastAPI:
    """工厂函数：构造 FastAPI 应用（也方便用 httpx TestClient 做单进程测试）。"""
    app = FastAPI(
        title="接口自动化测试平台 · 被测后端",
        description="小型电商后端（用户/商品/订单/支付），用于演示接口自动化测试。",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── 健康检查：BackendServer 就绪探测用 ──
    @app.get("/health", tags=["健康检查"])
    async def health():
        return {"status": "ok", "service": "api-test-platform-backend"}

    # ── 挂载路由 ──
    from apps.backend.routers import auth as _auth
    from apps.backend.routers import products as _products
    from apps.backend.routers import orders as _orders
    from apps.backend.routers import payment as _payment
    app.include_router(_auth.router)
    app.include_router(_products.router)
    app.include_router(_orders.router)
    app.include_router(_payment.router)

    return app


# uvicorn apps.backend.main:app 会找这个模块级变量
app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port)
