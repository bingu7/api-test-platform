"""随机数据工厂（Faker 风格，不依赖 Faker 库——标准库 secrets 凑够用）。

区别于 builders.py：
- builders 是「构造一组完整、合法的结构体」
- factories 是「凑一个随机值」（用户名/邮箱/订单号/金额），用于撞库场景

真实项目可换成 `from faker import Faker`；这里保持零依赖，便于学习时逐步引入。
"""
from __future__ import annotations

import random
import secrets
import string


def fake_username() -> str:
    """随机用户名：u + 8位随机。"""
    return "u" + secrets.token_hex(8)


def fake_email(domain: str = "example.com") -> str:
    """随机邮箱。"""
    return f"{secrets.token_hex(6)}@{domain}"


def fake_password(length: int = 12) -> str:
    """随机强密码（含大小写+数字）。"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def fake_order_id(prefix: str = "ORD") -> str:
    """业务订单号：前缀 + 16位随机。"""
    return f"{prefix}_{secrets.token_hex(8)}"


def fake_amount(min_v: float = 0.01, max_v: float = 999.99) -> float:
    """随机金额，保留两位小数。"""
    return round(random.uniform(min_v, max_v), 2)


def fake_idempotency_key() -> str:
    """随机幂等键。"""
    return "idem_" + secrets.token_hex(8)


def fake_product_name() -> str:
    """随机商品名。"""
    names = ["键盘", "鼠标", "显示器", "耳机", "充电器", "支架", "主机", "路由器"]
    return f"{secrets.choice(names)}_{secrets.token_hex(2)}"
