"""JSON Schema 响应结构校验 + 预定义 Schema 库。

与只断言 `assert data["orders"][0]["order_id"]` 不同：
- Schema 校验能发现字段类型变化（amount 从 int→string、多了/少了字段）
- 面试场景：「你如何保证接口没被改坏」→「我加了 Schema 校验层」
"""
from __future__ import annotations

import json

import allure
from jsonschema import validate, ValidationError
from requests import Response

from utils.assert_helpers import attach_response

# ── 预定义 Schema ──
SCHEMA_LOGIN_SUCCESS = {
    "type": "object",
    "required": ["code", "message", "access_token", "expires_in"],
    "properties": {
        "code": {"type": "integer", "enum": [0]},
        "message": {"type": "string"},
        "access_token": {"type": "string", "minLength": 1},
        "expires_in": {"type": "integer", "minimum": 1},
    },
    "additionalProperties": False,
}

SCHEMA_USER_PROFILE = {
    "type": "object",
    "required": ["code", "message", "data"],
    "properties": {
        "code": {"type": "integer"},
        "message": {"type": "string"},
        "data": {
            "type": "object",
            "required": ["username", "role"],
            "properties": {
                "username": {"type": "string"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
}

SCHEMA_ORDER = {
    "type": "object",
    "required": ["order_id", "amount", "status"],
    "properties": {
        "order_id": {"type": "string", "minLength": 1},
        "amount": {"type": "number", "exclusiveMinimum": 0},
        "status": {"type": "string", "enum": ["pending", "paid", "cancelled"]},
    },
    "additionalProperties": False,
}

SCHEMA_ORDERS_LIST = {
    "type": "object",
    "required": ["code", "message", "data"],
    "properties": {
        "code": {"type": "integer"},
        "message": {"type": "string"},
        "data": {
            "type": "object",
            "required": ["orders"],
            "properties": {
                "orders": {
                    "type": "array",
                    "minItems": 1,
                    "items": SCHEMA_ORDER,
                }
            },
        },
    },
}

SCHEMA_ERROR = {
    "type": "object",
    "required": ["code", "message"],
    "properties": {
        "code": {"type": "integer"},
        "message": {"type": "string"},
    },
}


def validate_response(response: Response, schema: dict, schema_name: str = "") -> dict:
    """校验响应体是否符合指定 Schema。

    Schema 校验包括：字段存在性 / 类型 / 枚举值 / 额外字段 / 数值范围
    - 通过: 返回 parsed payload
    - 失败: 抛出 AssertionError（含 schema_name + 具体差异）
    """
    try:
        payload = response.json()
    except ValueError:
        raise AssertionError(f"响应不是JSON: {response.text[:300]}")

    try:
        validate(instance=payload, schema=schema)
    except ValidationError as e:
        attach_response(response, name=f"Schema校验失败-{schema_name or 'unknown'}")
        raise AssertionError(
            f"Schema [{schema_name}] 校验失败:\n"
            f"  路径: {'.'.join(str(p) for p in e.absolute_path)}\n"
            f"  消息: {e.message}\n"
            f"  实例: {e.instance}\n"
            f"  完整响应: {json.dumps(payload, ensure_ascii=False)[:500]}"
        ) from e

    return payload