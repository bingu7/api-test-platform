"""真实环境接口测试 — 对接 jsonplaceholder.typicode.com。

运行方式：
  $env:TEST_ENV="test"
  python -m pytest tests/test_real_env.py -v

也可以在 CI 里：
  TEST_ENV=test bash scripts/ci_test.sh full

JSONPlaceholder 无需鉴权，所有请求传 auth=False。
"""
from __future__ import annotations

import time
import concurrent.futures

import allure
import pytest

from core.base_request import HttpClient
from utils.assert_helpers import assert_status, attach_response


@allure.epic("真实环境测试")
@allure.feature("JSONPlaceholder")
@pytest.mark.real_env
@pytest.mark.smoke
class TestPosts:
    """GET /posts — 100 条 / 支持 CRUD"""

    def test_get_all_posts(self, raw_client: HttpClient):
        response = raw_client.get("/posts", auth=False)
        assert_status(response, 200)
        posts = response.json()
        assert isinstance(posts, list) and len(posts) == 100

    def test_get_single_post(self, raw_client: HttpClient):
        response = raw_client.get("/posts/1", auth=False)
        assert_status(response, 200)
        post = response.json()
        assert post["userId"] == 1
        assert "title" in post and isinstance(post["title"], str)

    def test_create_post(self, raw_client: HttpClient):
        response = raw_client.post("/posts", auth=False, json={
            "title": "real-env-test", "body": "hello", "userId": 1,
        })
        assert_status(response, 201)
        assert response.json()["id"] == 101

    def test_update_post(self, raw_client: HttpClient):
        response = raw_client.put("/posts/1", auth=False, json={
            "id": 1, "title": "updated", "body": "...", "userId": 1,
        })
        assert_status(response, 200)
        assert response.json()["title"] == "updated"

    def test_delete_post(self, raw_client: HttpClient):
        response = raw_client.delete("/posts/1", auth=False)
        assert_status(response, 200)

    def test_nonexistent_post(self, raw_client: HttpClient):
        response = raw_client.get("/posts/99999", auth=False)
        assert_status(response, 404)

    def test_filter_by_user(self, raw_client: HttpClient):
        response = raw_client.get("/posts", auth=False, params={"userId": 1})
        assert_status(response, 200)
        assert all(p["userId"] == 1 for p in response.json())


@allure.epic("真实环境测试")
@allure.feature("JSONPlaceholder")
@pytest.mark.real_env
class TestComments:
    """GET /comments — 500 条"""

    def test_get_all(self, raw_client: HttpClient):
        response = raw_client.get("/comments", auth=False)
        assert_status(response, 200)
        assert len(response.json()) == 500

    def test_filter_by_post(self, raw_client: HttpClient):
        response = raw_client.get("/comments", auth=False, params={"postId": 1})
        assert_status(response, 200)
        comments = response.json()
        assert len(comments) == 5
        assert all(c["postId"] == 1 for c in comments)

    def test_structure(self, raw_client: HttpClient):
        response = raw_client.get("/comments/1", auth=False)
        assert_status(response, 200)
        keys = response.json().keys()
        assert keys >= {"postId", "id", "name", "email", "body"}


@allure.epic("真实环境测试")
@allure.feature("JSONPlaceholder")
@pytest.mark.real_env
class TestAlbumsAndPhotos:
    def test_get_albums(self, raw_client: HttpClient):
        response = raw_client.get("/albums", auth=False)
        assert_status(response, 200)
        assert len(response.json()) == 100

    def test_filter_by_user(self, raw_client: HttpClient):
        response = raw_client.get("/albums", auth=False, params={"userId": 3})
        assert_status(response, 200)
        assert all(a["userId"] == 3 for a in response.json())

    def test_get_photos(self, raw_client: HttpClient):
        response = raw_client.get("/photos", auth=False)
        assert_status(response, 200)
        assert len(response.json()) == 5000

    def test_photo_url_format(self, raw_client: HttpClient):
        response = raw_client.get("/photos/1", auth=False)
        assert_status(response, 200)
        p = response.json()
        assert p["url"].startswith("https://")
        assert p["thumbnailUrl"].startswith("https://")


@allure.feature("JSONPlaceholder")
@pytest.mark.real_env
class TestTodos:
    def test_get_all(self, raw_client: HttpClient):
        response = raw_client.get("/todos", auth=False)
        assert_status(response, 200)
        assert len(response.json()) == 200

    def test_completed_is_bool(self, raw_client: HttpClient):
        response = raw_client.get("/todos/1", auth=False)
        assert_status(response, 200)
        assert isinstance(response.json()["completed"], bool)


@allure.feature("JSONPlaceholder")
@pytest.mark.real_env
class TestUsers:
    def test_get_all(self, raw_client: HttpClient):
        response = raw_client.get("/users", auth=False)
        assert_status(response, 200)
        assert len(response.json()) == 10

    def test_nested_fields(self, raw_client: HttpClient):
        response = raw_client.get("/users/1", auth=False)
        assert_status(response, 200)
        u = response.json()
        assert u["company"]["name"] == "Romaguera-Crona"
        assert u["address"]["city"] == "Gwenborough"

    def test_filter_by_username(self, raw_client: HttpClient):
        response = raw_client.get("/users", auth=False, params={"username": "Bret"})
        assert_status(response, 200)
        users = response.json()
        assert len(users) == 1
        assert users[0]["name"] == "Leanne Graham"


@allure.feature("JSONPlaceholder")
@pytest.mark.real_env
class TestRelations:
    def test_posts_comments(self, raw_client: HttpClient):
        response = raw_client.get("/posts/1/comments", auth=False)
        assert_status(response, 200)
        assert len(response.json()) == 5

    def test_albums_photos(self, raw_client: HttpClient):
        response = raw_client.get("/albums/1/photos", auth=False)
        assert_status(response, 200)
        assert len(response.json()) == 50


@allure.epic("真实环境测试")
@allure.feature("实景性能")
@pytest.mark.real_env
class TestRealEnvPerformance:
    def test_latency_under_2s(self, raw_client: HttpClient):
        start = time.time()
        response = raw_client.get("/posts/1", auth=False)
        elapsed = time.time() - start
        assert_status(response, 200)
        assert elapsed < 2.0, f"耗时 {elapsed:.2f}s"

    @pytest.mark.slow
    def test_bulk_50_concurrent(self, raw_client: HttpClient):
        def fetch(n: int) -> bool:
            from core.base_request import HttpClient as H
            c = H(raw_client.base_url, token_manager=None, timeout=raw_client.timeout)
            try:
                return c.get(f"/posts/{n}", auth=False).status_code == 200
            finally:
                c.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            ok = sum(pool.map(fetch, range(1, 51)))
        assert ok == 50, f"Only {ok}/50 passed"


@allure.feature("JSONPlaceholder")
@pytest.mark.real_env
class TestErrorHandling:
    def test_404(self, raw_client: HttpClient):
        assert_status(raw_client.get("/not-exist", auth=False), 404)

    def test_jsonplaceholder_accepts_any_post_body(self, raw_client: HttpClient):
        response = raw_client.post("/posts", auth=False, json={
            "title": "", "body": "", "userId": "not-an-int",
        })
        assert_status(response, 201)