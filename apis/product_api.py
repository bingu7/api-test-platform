"""商品接口封装。

对应后端 apps/backend/routers/products.py：
- GET    /api/products          列表（公开）
- GET    /api/products/{id}     详情（公开）
- POST   /api/products          创建（仅 admin）
- PUT    /api/products/{id}     更新（仅 admin）
- DELETE /api/products/{id}     删除（仅 admin）

权限测试重点：create/update/delete 带 auth=True，普通用户得 403、无 token 得 401。
"""
from __future__ import annotations

from typing import Any

from requests import Response

from core.base_request import HttpClient


class ProductAPI:
    """商品接口封装类。"""

    def __init__(self, client: HttpClient):
        self.client = client

    def list(self, skip: int = 0, limit: int = 100, **kw: Any) -> Response:
        """商品列表（公开，auth=False）。支持分页。"""
        return self.client.get(
            "/api/products",
            auth=False,
            params={"skip": skip, "limit": limit},
            **kw,
        )

    def get(self, product_id: int, **kw: Any) -> Response:
        """商品详情（公开）。不存在返回 404。"""
        return self.client.get(f"/api/products/{product_id}", auth=False, **kw)

    def create(self, name: str, price: float, stock: int = 0, description: str = "",
               **kw: Any) -> Response:
        """创建商品（需 admin，auth=True）。普通用户得 403。"""
        return self.client.post(
            "/api/products",
            auth=True,
            json={"name": name, "price": price, "stock": stock, "description": description},
            **kw,
        )

    def update(self, product_id: int, data: dict, **kw: Any) -> Response:
        """更新商品（需 admin）。data 里只放要改的字段。"""
        return self.client.put(
            f"/api/products/{product_id}",
            auth=True,
            json=data,
            **kw,
        )

    def delete(self, product_id: int, **kw: Any) -> Response:
        """删除商品（需 admin）。不存在返回 404。"""
        return self.client.delete(f"/api/products/{product_id}", auth=True, **kw)
