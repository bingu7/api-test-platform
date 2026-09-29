# 学习路径：如何用这个仓库学接口自动化

目标：不是「会点运行 demo」，而是能说清每一层为什么这样设计，并能自给自足地给一个新 REST 后端写一套完整接口自动化。

建议总时长：**10 个晚上**，每天只做一节 + 一个小实验。完整阅读由此顺序：`README → ARCHITECTURE（主读）→ 本文 → BACKEND → FLOW → JENKINS`。

---

## 第 0 天：两个环境都跑通

```bash
# 装依赖
pip install -r requirements.txt
pip install -r apps/backend/requirements.txt

# dev（Flask Mock，零外网）
python -m pytest tests/ -v
# real（FastAPI 后端，自动起 + 全维度）
TEST_ENV=real python -m pytest tests/ -v
```

观察：

- dev 在数秒内跑完；real 多花几秒（起后端 + 接口真打）
- 各跑了几条用例，看状态码色块分布

---

## 第 1 天：配置与路径（`config/` + `utils/paths.py`）

**读**：`config/settings.py`、`utils/paths.py`

**实验**：
```powershell
$env:API_USERNAME="admin"
$env:API_PASSWORD="wrong"
python -m pytest tests/test_framework.py -v
```
观察：为什么不会污染——Windows 的 `USERNAME` 系统变量会怎样。

**自问**：
- `get_settings("no-such-env")` 为什么抛错而不是静默用 dev？
- 为什么是 `API_USERNAME` 而不是 `USERNAME`？

---

## 第 2 天：HttpClient 与 Token（`core/base_request.py` + `token_manager.py`）

**读**：HTTP 客户端的 Session/Retry/auth 设计；TokenManager 缓存与提前过期。

**实验**：在 `tests/` 临时写：
```python
def test_auth(raw_client, api_client):
    assert raw_client.get("/api/user/profile", auth=False).status_code == 401  # dev
    assert api_client.get("/api/user/profile", auth=True).status_code == 200
```

**自问**：登录负向用例为什么不能用 `auth=True`？Retry 为什么不含 401？

---

## 第 3 天：真实后端怎么写（`apps/backend/`）—— 关键一天

**读**：`main.py`（lifespan）/ `models.py`（ORM）/ `schemas.py`（Pydantic）/ `auth.py`（PBKDF2+JWT）/ `routers/`。

**实验**：
```bash
make backend
# 浏览器开 http://127.0.0.1:8000/docs，点 Authorize 试调 /api/orders
```

**自问**：
- IDOR 防护写在哪一行？为什么 `order.user_id != user.id` 就能防越权？
- 422 是 Pydantic 在哪一层拦下的？
- 幂等键为什么能防重复扣款？

---

## 第 4 天：接口封装层 PO 模式（`apis/`）

**读**：`apis/auth_api.py` / `order_api.py` —— 每个方法只封装「怎么调」。

**实验**：写一个新接口封装方法——比如 `OrderAPI.list_by_status`，再写测试调它。

**自问**：
- 把 PO 想成「service 层」，与「测试里直接 POST URL」相比，未来接口改路径谁省事？
- 为什么不把断言写进 PO？

---

## 第 5 天：数据驱动与断言（`utils/excel_reader.py` + `assert_helpers.py` + `data/builders.py`）

**读**：Excel 列约定；`filter_cases`；`assert_json_path` / `assert_response_time`；Builder 链式造数据。

**实验**：
- 在 `data/backend_cases.xlsx` 加一行用例（重复用户名注册）
- 用 `UserData().with_password("1").build()` 写一个 422 用例

**自问**：
- 业务 code 与 HTTP status 为什么都要断言？
- Builder 与随机 Factory 各自适合什么场景？

---

## 第 6 天：Mock 与 fixture（`core/mock_server.py` + `conftest.py`）

**读**：session 级 `mock_server` / `backend_server` fixture；环境 marker 怎么分发用例。

**实验**：把 `mock_server` fixture 的 `scope` 改成 `function` 跑一次——感受耗时差异。

**自问**：
- 为什么 conftest 自动起后端，而不是 Jenkins 配置里起？
- `pytest_collection_modifyitems` 怎么做到「dev 不跑后端、real 不跑 Mock」？

---

## 第 7 天：DB 落库白盒校验（`utils/db_helper.py` + `tests/test_db_verification.py`）

**读**：直连 SQLite 做只读断言；API 返回 + DB 状态双校验。

**实验**：写一个 `test_refund_then_db`——调退款然后 `db_helper.assert_payment_status(refunded)`。

**自问**：
- 为什么 HTTP 200 不代表数据真的落库？
- 双校验里哪一项更可信？

---

## 第 8 天：安全 / 性能 / 契约测试（多维）

**读**：
- `tests/test_security.py`——IDOR / 越权 / SQL注入 / 泄露 / 鉴权
- `tests/test_performance.py` + `scripts/perf_test.py`——P95 / QPS
- `tests/test_contract.py`——OpenAPI 契约

**实验**：
- 故意把后端某行 `order.user_id != user.id` 校验去掉，跑 `test_security.py` 看哪条挂
- 改 `perf_test.py` 的 `-n`、`-c` 看响应如何随并发变化
- 在 `/openapi.json` 里找一个端点，看响应结构是否和契约对得上

**自问**：
- 接口测试里，「安不安全」和「正不正常」是同一回事吗？
- 契约漂移和业务功能性 fail 区别在哪？

---

## 第 9 天：自己加一个完整的新接口（端到端演练）

按正规流程加一条「商品搜索」接口，从头到尾都碰一遍：

1. 后端：`routers/products.py` 加 `GET /api/products/search?q=...`
2. PO：`apis/product_api.py` 加 `search(q)` 方法
3. 数据：`data/builders.py` 加 `ProductData.with_name`
4. 测试：
   - `test_product_api.py` 正向 + 测权限边界
   - `test_contract.py` 拉新端点的 OpenAPI 校验
   - `test_performance.py` 给它加个基准断言（> 200ms 算失败）
5. 标 marker：`backend` + `smoke`
6. 跑：`TEST_ENV=real pytest -m smoke`

做完后你应能向面试官讲清：

> 配置 → 客户端 → 后端 → PO → 数据 → DB校验 → 断言 → 报告 → CI 全链路

---

## 第 10 天：CI / Jenkins / 完整交付

**读**：[FLOW.md](./FLOW.md) / [JENKINS.md](./JENKINS.md) / 根 `Jenkinsfile` / `.github/workflows/api-tests.yml` / `scripts/ci_test.*`。

**实验**：
```bash
scripts/ci_test.bat full           # dev
TEST_ENV=real scripts/ci_test.sh full   # real
dir reports
dir allure-results
allure serve allure-results        # 看可视化报告
```

**自问**：
- 为什么 CI 不在 Jenkinsfile 里直接写长 pytest，而是抽到 `scripts/`？
- smoke vs full 在什么门禁各适合？
- matrix 跑两 env 的成本与价值？

---

## 推荐阅读顺序（源文件）

```
README.md
docs/ARCHITECTURE.md          ← 你在这里上面的
docs/LEARNING.md              ← 本文
docs/BACKEND.md
config/settings.py
utils/paths.py  utils/logger.py
core/token_manager.py
core/base_request.py
apps/backend/main.py  models.py  schemas.py  deps.py  routers/
core/mock_server.py
core/backend_server.py
conftest.py
apis/auth_api.py  order_api.py
data/builders.py  factories.py
utils/assert_helpers.py  db_helper.py  schema_validator.py
tests/test_auth_api.py  test_order_api.py  test_payment_api.py
tests/test_db_verification.py  test_security.py  test_performance.py  test_contract.py
```

---

## 反模式清单（项目里已避免，别加回去）

| 反模式 | 正规做法 |
|--------|---------|
| 登录测试强制带 Bearer | `auth=False` / `raw_client` |
| 每文件起一个 Mock 固定端口 | session 级 + 随机端口 |
| `localhost` | `127.0.0.1` |
| Excel 相对 cwd | `data_file()` / 绝对路径 |
| Token 失败 `KeyError` | `TokenError` + 状态码/body |
| 测试里直接写 URL / body | `apis/` PO 封装 |
| 只断言 HTTP 200 | 加 DB 白盒 (db_helper) |
| 每次跑用例用固定账号 | `factories.fake_*()` 随机 |
| 测接口不测安全 | `test_security.py` 越权/注入/泄露 |
| 本机一套命令、CI 另一套 | 统一 `scripts/ci_test.*` |
| 把后端进程依赖 Jenkins 配 | conftest fixture 自动起 |

---

## 学完后能向面试官讲清

| 问题 | 指哪 |
|------|------|
| 接口之间怎么串联 | `test_workflow.py`、`test_auth_api.py::test_login_then_me` |
| 怎么保证数据真的落库 | `test_db_verification.py` |
| 接口安全怎么测 | `test_security.py` |
| 性能怎么测 | `test_performance.py` + `perf_test.py` |
| 契约怎么不漂 | `test_contract.py` |
| 接口怎么封装 | `apis/` PO 模式 |
| 多环境怎么切 | `TEST_ENV` + conftest |
| CI 怎么交付 | `Jenkinsfile` + `scripts/ci_test.*` |

每问只答一文件 —— 这是「能讲清每一层为什么」的具体落地。
