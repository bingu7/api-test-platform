"""接口性能/压测维度测试（real 环境）。

学习重点——接口测试里的性能断言：
- 单接口基准：P95 延迟必须在阈值内（如 < 500ms）
- 并发吞吐：N 个并发请求在合理时间内完成、成功率达标
- 响应时间断言：assert_response_time
"""
from __future__ import annotations

import concurrent.futures
import statistics
import time

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_response_time, assert_status, attach_response

pytestmark = [pytest.mark.backend, pytest.mark.performance]


@allure.feature("性能")
@allure.story("单接口基准")
class TestLatencyBaseline:
    @allure.title("商品列表响应 < 500ms")
    @pytest.mark.smoke
    def test_list_latency(self, raw_client: HttpClient):
        r = raw_client.get("/api/products", auth=False)
        attach_response(r)
        assert_status(r, 200)
        ms = assert_response_time(r, max_ms=500)
        allure.attach(f"{ms:.1f}ms", name="响应时间", attachment_type=allure.attachment_type.TEXT)

    @allure.title("登录响应 < 800ms")
    def test_login_latency(self, raw_client: HttpClient):
        r = raw_client.post("/api/auth/login", auth=False,
                             json={"username": "admin", "password": "admin123"})
        assert_status(r, 200)
        # 登录涉及 bcrypt-like 哈希校验，留足余量
        assert_response_time(r, max_ms=800)


@allure.feature("性能")
@allure.story("并发吞吐")
class TestConcurrency:
    @allure.title("20 并发 100 次商品列表 → 成功率 >= 95%、P95 < 1s")
    @pytest.mark.smoke
    def test_concurrent_list(self, raw_client: HttpClient):
        n, c = 100, 20

        def one(_):
            t = time.perf_counter()
            try:
                r = raw_client.get("/api/products", auth=False, timeout=10)
                ok = r.status_code == 200
            except Exception:
                ok = False
            return time.perf_counter() - t, ok

        with concurrent.futures.ThreadPoolExecutor(max_workers=c) as pool:
            results = list(pool.map(one, range(n)))

        latencies = [x for x, _ in results]
        ok = sum(1 for _, o in results if o)
        success_rate = ok / n
        sorted_l = sorted(latencies)
        p95 = sorted_l[int(len(sorted_l) * 0.95)]

        allure.attach(
            f"n={n} c={c}\nok={ok} 失败={n-ok}\n成功率={success_rate*100:.1f}%\nP95={p95*1000:.1f}ms",
            name="压测报告",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert success_rate >= 0.95, f"成功率 {success_rate*100:.1f}% < 95%"
        assert p95 < 1.0, f"P95 {p95*1000:.1f}ms 超过 1s"

    @allure.title("30 并发登录 → 全部 200（无 session 串扰）")
    @pytest.mark.slow
    def test_concurrent_login(self, raw_client: HttpClient):
        n, c = 30, 10

        def one(_):
            from core.base_request import HttpClient as H
            cl = H(raw_client.base_url, token_manager=None, timeout=raw_client.timeout)
            try:
                r = cl.post("/api/auth/login", auth=False,
                            json={"username": "admin", "password": "admin123"})
                return r.status_code == 200
            finally:
                cl.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=c) as pool:
            oks = list(pool.map(one, range(n)))
        assert all(oks), f"{sum(1 for o in oks if not o)}/{n} 失败"
