"""utils/assert_helpers.py 的单元测试（纯函数，不依赖被测系统）。

为什么单独一个文件：
- 断言助手是「测试的测试」——它自己错了，会让所有用例的结论不可信。
  之前 _resolve_path 只能解析末级下标，中间级 a[0].b 全废，但因为没人调用、
  也没人测它，这个 bug 一直潜伏。这里把路径解析的各种写法钉死。
- 本文件不打 mock_only / backend 标记：纯函数测试在三个环境都该跑。

覆盖重点（回归）：
    data.orders[0].order_id      ← 修复前必挂，核心回归点
    data.orders[0].items[1].name ← 多级下标连续出现
"""
from __future__ import annotations

import json

import pytest
import requests

from utils.assert_helpers import (
    _resolve_path,
    _tokenize_path,
    assert_business,
    assert_detail,
    assert_json_path,
    assert_paginated_list,
    assert_response_time,
    assert_status,
)


def _make_response(payload=None, status: int = 200, elapsed: float = 0.01) -> requests.Response:
    """造一个带 json 体 / 状态码 / 耗时的 requests.Response，用于纯函数测试。"""
    resp = requests.Response()
    resp.status_code = status
    if payload is not None:
        resp._content = json.dumps(payload).encode("utf-8")
    resp.headers["Content-Type"] = "application/json"
    resp.request = requests.Request("GET", "http://127.0.0.1:1/api/fake").prepare()
    resp.elapsed = __import__("datetime").timedelta(seconds=elapsed)
    return resp


# 一份贴近真实接口的响应：Mock 是 {code, message, data:{orders:[...]}} 两层嵌套
ORDERS_PAYLOAD = {
    "code": 0,
    "message": "获取成功",
    "data": {
        "orders": [
            {
                "order_id": "O1",
                "amount": 10.0,
                "items": [{"name": "n0"}, {"name": "n1"}],
            },
            {"order_id": "O2", "amount": 20.0, "items": []},
        ]
    },
}


class TestResolvePath:
    """路径解析的核心行为。"""

    @pytest.mark.parametrize(
        "path, expected",
        [
            # ── 基础：点号字段名 ──
            ("data", ORDERS_PAYLOAD["data"]),
            ("data.orders", ORDERS_PAYLOAD["data"]["orders"]),
            ("code", 0),
            # ── 末级下标（修复前就支持，防止回归） ──
            ("data.orders[0]", ORDERS_PAYLOAD["data"]["orders"][0]),
            ("data.orders[1].order_id", "O2"),
            # ── 中间级下标（修复前必挂，核心回归点） ──
            ("data.orders[0].order_id", "O1"),
            ("data.orders[0].amount", 10.0),
            # ── 多级下标连续出现 ──
            ("data.orders[0].items[1].name", "n1"),
            ("data.orders[0].items[0].name", "n0"),
            # ── 根就是数组/标量 ──
            ("data.orders[0].items", [{"name": "n0"}, {"name": "n1"}]),
        ],
    )
    def test_supported_paths(self, path, expected):
        assert _resolve_path(ORDERS_PAYLOAD, path) == expected

    @pytest.mark.parametrize(
        "path",
        [
            "$.data.orders[0].order_id",
            "$data.orders[0].order_id",
        ],
    )
    def test_jsonpath_dollar_prefix(self, path):
        """兼容从别处抄来的 JSONPath 写法（$ 前缀）。"""
        assert _resolve_path(ORDERS_PAYLOAD, path) == "O1"

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("data['orders'][0].order_id", "O1"),
            ('data["orders"][0].order_id', "O1"),
            ("data.orders[ 0 ].order_id", "O1"),  # 括号内允许空白
        ],
    )
    def test_bracket_forms(self, path, expected):
        """单/双引号字符串 key、括号内空白都应支持。"""
        assert _resolve_path(ORDERS_PAYLOAD, path) == expected

    def test_string_key_with_dot_inside(self):
        """key 本身含点号时必须用引号包起来——否则和路径分隔符歧义。"""
        data = {"a.b": "dotted", "a": {"b": "nested"}}
        assert _resolve_path(data, "['a.b']") == "dotted"
        assert _resolve_path(data, "a.b") == "nested"

    def test_negative_index_rejected_as_syntax(self):
        """不支持负索引：应明确报语法/解析错，而不是静默取到错误的值。"""
        with pytest.raises((ValueError, KeyError, IndexError)):
            _resolve_path(ORDERS_PAYLOAD, "data.orders[-1]")

    # ── 错误路径：必须抛异常，不能静默返回 None ──

    def test_missing_field_raises_keyerror(self):
        with pytest.raises(KeyError, match="不存在的字段"):
            _resolve_path(ORDERS_PAYLOAD, "data.不存在的字段")

    def test_index_out_of_range(self):
        with pytest.raises(IndexError, match="下标越界"):
            _resolve_path(ORDERS_PAYLOAD, "data.orders[99]")

    def test_scalar_traversal_raises_typeerror(self):
        with pytest.raises(TypeError, match="无法用"):
            _resolve_path(ORDERS_PAYLOAD, "data.orders[0].order_id.deeper")

    @pytest.mark.parametrize("bad", ["", "   ", "$", "a[", "a]", "a..[0]"])
    def test_malformed_path_raises_valueerror(self, bad):
        """路径语法错要抛 ValueError——让「路径写错」和「响应结构不对」可区分。"""
        with pytest.raises(ValueError):
            _resolve_path(ORDERS_PAYLOAD, bad)

    def test_error_message_contains_position(self):
        """报错要能指出走到哪一步失败，否则排障很痛苦。"""
        with pytest.raises(KeyError) as ei:
            _resolve_path(ORDERS_PAYLOAD, "data.orders[0].nope")
        assert "data.orders[0]" in str(ei.value)


class TestTokenizePath:
    """分词器本身（_resolve_path 的第一阶段）。"""

    def test_splits_fields_and_indices(self):
        assert _tokenize_path("data.orders[0].order_id") == [
            ("key", "data"),
            ("key", "orders"),
            ("index", 0),
            ("key", "order_id"),
        ]

    def test_index_only_path(self):
        assert _tokenize_path("[3]") == [("index", 3)]

    def test_quoted_key_keeps_dot(self):
        assert _tokenize_path("['a.b']") == [("key", "a.b")]


class TestAssertJsonPath:
    """对外断言函数：成功返回 payload，失败抛 AssertionError 且信息可读。"""

    def test_passes_and_returns_full_payload(self):
        resp = _make_response(ORDERS_PAYLOAD)
        payload = assert_json_path(resp, "data.orders[0].order_id", "O1")
        assert payload == ORDERS_PAYLOAD, "应返回完整 payload 便于继续断言"

    def test_value_mismatch_reports_expected_and_actual(self):
        resp = _make_response(ORDERS_PAYLOAD)
        with pytest.raises(AssertionError) as ei:
            assert_json_path(resp, "data.orders[0].order_id", "WRONG")
        msg = str(ei.value)
        assert "WRONG" in msg and "O1" in msg, f"报错应同时含期望/实际值: {msg}"

    def test_missing_field_becomes_assertion_error_not_keyerror(self):
        """测试代码期望的是 AssertionError（断言失败），不是 KeyError 崩栈。"""
        resp = _make_response(ORDERS_PAYLOAD)
        with pytest.raises(AssertionError, match="解析失败"):
            assert_json_path(resp, "data.orders[0].ghost", "x")

    def test_syntax_error_has_distinct_message(self):
        """路径写错 vs 响应结构不对，报错要能一眼区分。"""
        resp = _make_response(ORDERS_PAYLOAD)
        with pytest.raises(AssertionError, match="语法非法"):
            assert_json_path(resp, "data.orders[", "x")

    def test_non_json_body_reports_assertion_error(self):
        resp = _make_response(None)
        resp._content = b"<html>502 Bad Gateway</html>"
        with pytest.raises(Exception) as ei:
            assert_json_path(resp, "a", 1)
        assert not isinstance(ei.value, KeyError), "不该把非 JSON 报成 KeyError"


class TestOtherHelpers:
    """顺带钉住其余断言助手的基本契约。"""

    def test_assert_status_pass_and_fail(self):
        assert_status(_make_response({"ok": True}, status=200), 200)
        with pytest.raises(AssertionError, match="状态码不符"):
            assert_status(_make_response({"ok": True}, status=500), 200)

    def test_assert_business_code_and_message(self):
        resp = _make_response({"code": -1, "message": "用户名或密码错误"})
        payload = assert_business(resp, expected_code=-1, expected_msg_contains="密码错误")
        assert payload["code"] == -1

    def test_assert_business_reads_fastapi_detail_shape(self):
        """FastAPI 原生错误用 {"detail": ...}，Mock 用 {"message": ...}，两套都要认。"""
        resp = _make_response({"detail": "订单不存在"})
        assert_business(resp, expected_msg_contains="订单不存在")

    def test_assert_business_detail_list_is_stringified(self):
        """422 的 detail 是 list，不能因为类型不是 str 就炸。"""
        resp = _make_response({"detail": [{"msg": "field required", "loc": ["body"]}]})
        assert_business(resp, expected_msg_contains="field required")

    def test_assert_detail(self):
        resp = _make_response({"detail": "订单号已存在"})
        assert_detail(resp, "订单号已存在")
        with pytest.raises(AssertionError):
            assert_detail(resp, "不存在的关键词")

    def test_assert_paginated_list(self):
        resp = _make_response([{"id": 1}, {"id": 2}])
        items = assert_paginated_list(resp, min_items=2)
        assert len(items) == 2
        with pytest.raises(AssertionError):
            assert_paginated_list(resp, min_items=5)

    def test_assert_paginated_list_rejects_non_list(self):
        with pytest.raises(AssertionError, match="期望列表"):
            assert_paginated_list(_make_response({"data": []}))

    def test_assert_response_time(self):
        ms = assert_response_time(_make_response({"ok": 1}, elapsed=0.05), max_ms=500)
        assert 40 <= ms <= 60
        with pytest.raises(AssertionError, match="超过阈值"):
            assert_response_time(_make_response({"ok": 1}, elapsed=1.0), max_ms=100)
