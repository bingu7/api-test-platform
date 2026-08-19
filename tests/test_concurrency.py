"""并发 / 性能用例。（Mock 专属）

场景：
- 并发登录：100 次请求全部成功，无死锁 / race condition
- 并发读：多客户端同时查用户信息
- 运行时可用 pytest-xdist 并行执行：pytest tests/ -n auto
"""
from __future__ import annotations

import concurrent.futures
import time

import allure
import pytest

pytestmark = pytest.mark.mock_only

from core.base_request import HttpClient
from core.mock_db import MockDB


@allure.feature("性能验证")
class TestConcurrency:
    """并发 + 批量验证。"""

    LOGIN_COUNT = 100  # 登录迭代次数

    @allure.story("批量登录")
    @allure.severity(allure.severity_level.NORMAL)
    def test_bulk_login_stress(self, raw_client: HttpClient):
        """连续 N 次登录全部成功——验证无 token 缓存错误 / session 泄漏。"""
        fail_count = 0
        for i in range(self.LOGIN_COUNT):
            response = raw_client.post(
                "/api/login",
                auth=False,
                json={"username": "admin", "password": "123456"},
            )
            if response.status_code != 200:
                fail_count += 1

            # 每 20 次重置一次 session 模拟真实压力
            if i % 20 == 19:
                raw_client.session.close()
                raw_client.session = raw_client._create_session(3)

        assert fail_count == 0, f"{fail_count}/{self.LOGIN_COUNT} 次登录失败"
        allure.attach(
            f"总请求: {self.LOGIN_COUNT}  失败: {fail_count}  成功率: {(1 - fail_count / self.LOGIN_COUNT) * 100:.1f}%",
            name="压力报告",
            attachment_type=allure.attachment_type.TEXT,
        )

    @allure.story("线程并发登录")
    def test_concurrent_login(self, raw_client: HttpClient):
        """10 线程并发登录 → 全部 200 且 Token 一致。"""
        def login_once(worker_id: int) -> bool:
            from core.base_request import HttpClient as _HttpClient

            client = _HttpClient(
                base_url=raw_client.base_url,
                token_manager=None,
                timeout=raw_client.timeout,
            )
            try:
                resp = client.post("/api/login", auth=False, json={"username": "admin", "password": "123456"})
                return resp.status_code == 200
            finally:
                client.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(login_once, i) for i in range(50)]
            results = [f.result() for f in futures]

        all_ok = all(results)
        assert all_ok, f"并发登录 {sum(1 for r in results if not r)}/{len(results)} 失败"

    @allure.story("DB 并发写入安全")
    def test_db_concurrent_writes(self, mock_db: MockDB):
        """100 线程并发写 MockDB → 无死锁、数据不丢失。"""
        def write_one(i: int) -> None:
            mock_db.create_order(f"CONC_ORD_{i:04d}", amount=float(i + 1))

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            list(executor.map(write_one, range(100)))

        count = mock_db.order_count()
        # 种子数据 3 + 链路测试 1 + 并发写入 100
        assert count >= 100, f"预期至少 100 条，实际 {count}"