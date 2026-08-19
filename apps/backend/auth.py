"""认证工具：密码哈希（PBKDF2）+ JWT 签发/校验。

为什么不用 bcrypt / passlib？
- 这台机器是 Python 3.14（很新），bcrypt 的 C 扩展可能没有预编译轮子，
  装不上会卡住整个学习流程。
- 标准库 hashlib.pbkdf2_hmac 同样是生产级方案（Django 默认就是 PBKDF2），
  纯 Python、零依赖、跨版本稳定，适合教学项目。
- 真实项目里如果你有 bcrypt 可用，把下面两个函数换成 passlib 即可，接口不变。

JWT 用 PyJWT + HS256（HMAC-SHA256）：纯 Python，不需要 cryptography 的 C 扩展。
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Any

import jwt

# ── 配置 ──
# 密钥：可用环境变量覆盖；默认值仅供本地演示，请勿用于真实生产。
SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-please-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# PBKDF2 参数：迭代次数越高越抗暴力破解，Django 默认 720000+。
PBKDF2_ITERATIONS = 260_000
DK_SIZE = 32  # 派生密钥长度（字节）


def hash_password(password: str) -> str:
    """对密码做 PBKDF2-HMAC-SHA256 哈希，返回 'pbkdf2_sha256$迭代次数$盐$哈希' 格式字符串。

    这个格式和 Django 兼容，便于理解：算法、轮数、盐、派生值都写进结果里。
    """
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"),
                             PBKDF2_ITERATIONS, dklen=DK_SIZE)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """校验明文密码是否匹配已存哈希。常量时间比较，防时序攻击。"""
    try:
        algo, iters, salt, hash_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"),
                             int(iters), dklen=len(bytes.fromhex(hash_hex)))
    return secrets.compare_digest(dk.hex(), hash_hex)


def create_access_token(data: dict[str, Any], expires_minutes: int | None = None) -> str:
    """签发 JWT。data 会被写进 payload，通常放 user_id / username / role。"""
    to_encode = data.copy()
    expire = time.time() + (expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    to_encode.update({"exp": int(expire), "iat": int(time.time())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """校验并解码 JWT。过期/非法会抛 jwt 异常（由调用方转成 HTTP 401）。"""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
