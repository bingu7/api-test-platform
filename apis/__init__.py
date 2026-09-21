"""接口封装层（服务对象模式 / PO 模式）。

为什么要有这一层（学习重点）：
- 测试里直接写 `client.post("/api/orders", json={...})` 会把「怎么调接口」和「校验什么」混在一起。
- 把每个模块的接口调用封装成类方法（如 OrderAPI.create_order），「怎么调」只写一次，
  测试只需「调方法 + 断言响应」——职责清晰，接口变了只改 apis/ 一处。
- 这就是真实项目里的接口对象 / service 层，面试加分点。

每个封装方法都返回 requests.Response，断言留在测试侧做（不在这层写 assert）。
"""
from apis.auth_api import AuthAPI
from apis.product_api import ProductAPI
from apis.order_api import OrderAPI
from apis.payment_api import PaymentAPI

__all__ = ["AuthAPI", "ProductAPI", "OrderAPI", "PaymentAPI"]
