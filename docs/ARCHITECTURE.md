# 架构详解：为什么每一层这样设计

这是你学习这个项目的**主读文档**。每一节回答「为什么」而不是「是什么」——前者决定能不能复用到别的项目。

---

## 总览：分层即分工

接口自动化不是「写一堆测试」就完事，而是把**可变的部分**和**稳定的部分**拆开：

```
[稳定]  配置 → 客户端 → 被测系统 → 接口封装 → 数据层工具 → 断言
                                                    │
[可变]  Excel/Builders → 具体测试用例 → 报告
```

每换一个被测系统，你只需要改「被测系统 + 接口封装 + 测试用例」，其余层不动；每换一套环境（dev/real/test），只需要改「配置」，其余层不动。这是「可工程化、可上线」与「跑通即可」的本质区别。

---

## 第 1 层 · 配置层 `config/settings.py`

**为什么**：测试不能写死「`base_url="http://127.0.0.1:5000"`」。要在多环境间切——本地、真后端、公开 API、上线环境——只需要改环境变量，不动代码。

**怎么做**：

- `Settings` 用 `@dataclass(frozen=True)`，配置对象不可变——测试中读不会意外改字段。
- 各环境默认值放进 `_DEFAULTS` 字典，env 变量比默认值优先（`_env(key, default)`）。
- 关键坑：**不能用 `USERNAME` 作 env 变量**——Windows 会注入当前系统用户名污染。统一用 `API_USERNAME`。

**环境切换**：

```bash
TEST_ENV=dev     # Flask Mock
TEST_ENV=real    # FastAPI 后端（conftest 子进程起）
TEST_ENV=test    # jsonplaceholder
TEST_ENV=staging # 自定义 BASE_URL
```

---

## 第 2 层 · 基础设施层 `core/`

### HttpClient `core/base_request.py`

**为什么**：不想每个测试都 `import requests; requests.get(...)` 重新建 session、设 retry、设 timeout。

**怎么做**：

- `requests.Session` 复用 → 自动 keep-alive + cookie。
- `trust_env=False` → 不被本机代理 / `$HTTP_PROXY` 污染（CI 必踩坑）。
- `Retry(total=3, status_forcelist=[500,502,503])` → 网络/服务端临时故障自动重试；
  **不含 504** → 业务超时若进重试会把一次变成多次。
- `auth=True/False` → 鉴权接口和登录/公开接口分流；
  收到 401 时自动 `token_manager.invalidate()` 重登一次（防 token 失效死循环）。
- 一把 `get/post/put/delete/patch` 便捷方法。

### TokenManager `core/token_manager.py`

**为什么**：登录返回的 token 不该每次请求都重新登录。

**怎么做**：

- 缓存 token + `expires_at`，提前 60s 过期（`skew_seconds`）防临界点失效。
- `invalidate()` 强制下次刷新——配合 HttpClient 401 自动重登。
- 失败抛 `TokenError`（带 status/body），不是裸 `KeyError`——错误信息可定位。

### MockServer `core/mock_server.py`

**为什么**：没真实后端时也能本地跑测试——Flask 起一个假 API，模拟登录/订单/支付/边界。

**怎么做**：

- `port=None` → 系统分配空闲端口（避免多 worker 抢端口）。
- `start()` 后 `_wait_ready` 同步探测 `/health`，避免测试抢跑。
- 限流、动态 token、IDOR 接口全实现——这些是接口测试的对象，Mock 也得能演。
- **session 级 fixture**：整个测试 session 复用一个，1s 内联调。

### BackendServer `core/backend_server.py`（新增）

**为什么**：真后端是另一个进程（FastAPI + uvicorn），不能和 Mock 一样塞 conftest 同进程跑——要起子进程、就绪、测完优雅关。

**怎么做**：

- `subprocess.Popen([sys.executable, "-m", "uvicorn", ...])`。
- `_wait_ready` 轮询 `/health` 直到 200；进程中途挂了直接抛错（带 stdout）。
- `stop()` 先 `terminate`，超时 `kill`，避免残留进程占用端口。
- 启动前删 `dev.db` 文件——后端 lifespan 会 `reset_and_seed` 重建一个干净库，保证测试隔离。

---

## 第 3 层 · 被测系统

### 真实后端 `apps/backend/`（新增）

**为什么**：测真实 REST API 才是上线场景。Mock 永远是「不真实」的——它没有 JWT、没有 SQL、没有 Pydantic 校验、没有真实的 422。后端写一个完整的小电商，既能学被测系统怎么写，又能拿来测。

**结构**（10 个文件）：

| 文件 | 职责 | 接口测试考点 |
|------|------|-------------|
| `main.py` | FastAPI app + lifespan | 启动建表灌种子；`/health` 探测；`/openapi.json` 契约源 |
| `database.py` | async SQLAlchemy + aiosqlite | 连接池管理；建表逻辑 |
| `models.py` | ORM: User/Product/Order/Payment | `Order.user_id` 体现归属（IDOR 防护点）；状态枚举 |
| `schemas.py` | Pydantic 模型 | 这一层就是接口契约；422 校验发生在这里 |
| `auth.py` | PBKDF2 + JWT | 真实鉴权算法 |
| `deps.py` | 依赖注入 | `get_current_user` → 401；`require_admin` → 403 |
| `routers/auth.py` | 注册/登录/me | 用户枚举防护（统一错误文案） |
| `routers/products.py` | 商品 CRUD | 公开读 vs admin 写的权限隔离 |
| `routers/orders.py` | 订单 | **IDOR 防护核心**：只准操作本人订单 |
| `routers/payment.py` | 支付/退款 | **幂等性**：同 idempotency_key 不重复扣款 |

**真实点**（面试能讲）：

- HTTP 400/401/403/404/422/429 状态码都在
- JWT 过期/伪造全部校验
- SQL 注入天然防（SQLAlchemy 参数化）
- 密码哈希存库（不出现在响应里、不可逆）
- 幂等键防重复扣款

### Flask Mock

保留作为 `dev` 环境离线备用——网断、CI 轻量跑、学习基础维度用。

---

## 第 4 层 · 接口封装层 `apis/`（新增，PO 模式）

**为什么**：测试里直接 `client.post("/api/orders", json={"order_id":"O1",...})` ❌——把「怎么调」和「校验什么」混在最容易变的地方。

**怎么做**：每个模块一个类，方法只封装调用：

```python
order_api = OrderAPI(api_client)
r = order_api.create("O1", amount=50.0)   # 「怎么调」只写一次
# 测试只写
assert_status(r, 201)
assert r.json()["status"] == "pending"
```

**职责清晰**：

- `apis/` 管「怎么调」（URL / method / 必填字段）
- `tests/` 管「调完什么该对」（断言）

接口变了（比如 `/api/orders` 改成 `/api/v2/orders`）→ 只改 `apis/order_api.py` 一文件，所有测试不动。

---

## 第 5 层 · 数据层 `data/`

三种数据来源共存，按场景选：

| 方式 | 文件 | 适用 |
|------|------|------|
| Excel 数据驱动 | `test_cases.xlsx` / `backend_cases.xlsx` | 大量相似用例、非开发同学能改 |
| Builder 模式 | `builders.py` | 造一组完整合法结构体（默认值 + 链式覆写） |
| 随机工厂 | `factories.py` | 凑随机值，避免脏数据撞库 |

### 为什么 Builder 默认值就是合法的

`UserData().with_password("1").build()` —— 你只想测「短密码 → 422」，其余字段（username/email）Builder 给你凑合法默认。

负面测试显式覆写你要测烂的那一项，正面测试啥都不覆写就行。

### Excel 路径为什么走 `utils/paths`

测试可能在项目不同子目录跑（`pytest tests/` / `pytest tests/test_login.py`），cwd 不固定。`data_file("xxx.xlsx")` 返回基于 `PROJECT_ROOT` 的绝对路径，无论在哪跑都找得到。

---

## 第 6 层 · 工具层 `utils/`

### 断言助手 `assert_helpers.py`

减少重复样板：

- `assert_status` / `assert_business`（code/msg）
- `assert_detail`（FastAPI 报错 `{detail: ...}`）
- `assert_json_path`（JSONPath 式：`data.orders[0].order_id`）—— 轻量自实现，不引依赖
- `assert_response_time`（性能断言）
- `attach_response`（响应贴 Allure 附件）

### Schema 校验 `schema_validator.py`

「只断 `code==0` 看不出 amount 从数字变字符串」——用 JSON Schema 校验类型 / 枚举 / 必填 / 额外字段。

### DB 白盒 `db_helper.py`（新增）

**接口测试金科玉律**：HTTP 200 不代表数据落库了。

用直连 SQLite 做只读断言——`assert_order_status(oid, "paid")`、`count_orders(user_id)`、`get_latest_payment(oid)`。配合接口返回，组成「API 返回 + DB 实际状态」双校验。

---

## 第 7 层 · 测试用例 `tests/`

按维度组织（详见 README 矩阵）。几个层次：

1. **接口层**（`test_*_api.py`）—— PO 模式 + 断言
2. **维度层**——DB / 安全 / 性能 / 契约 / 数据准备
3. **整合层**——`test_workflow.py` 全链路（Mock 环境）

### marker 怎么分发

`conftest.py` 的 `pytest_collection_modifyitems` 在用例收集后按 `TEST_ENV` 跳过不相干的：

- `dev` → 跑 `mock_only`，跳过 `real_env` + `backend`
- `real` → 跑 `backend`，跳过 `mock_only` + `real_env`
- `test/staging` → 跑 `real_env`，跳过 `mock_only` + `backend`

这样你的用例永远跑在合适的被测系统上，不会误打错目标。

---

## 第 8 层 · CI/CD

`scripts/ci_test.sh` / `.bat` 是**本机 / Jenkins / GitHub Actions 共用**入口——保证「本机绿、CI 绿」一致。

产物：`reports/junit.xml`（趋势图）+ `allure-results/`（详细报告）+ job 级邮件（`NOTIFY_EMAIL`）。

---

## 一图全流程

需求/改动 → 改对应层 → 本机 `pytest -m smoke` → 本机 `pytest` 全量
    → `scripts/ci_test` 模拟 CI → 推送 → Jenkins / GH Actions
    → JUnit + Allure 报告 → 缺陷 / 邮件

---

## 你学完应该会的迁移

1. 给一个全新 REST 后端写接口自动化：照 `apps/` 不一定要——照 `apis/` + `tests/test_*_api.py` + `data/builders.py` 直接纲。
2. 多环境部署：加 `_DEFAULTS["prod"]`、改 `tests/` 加新 marker。
3. 接入真实第三方 API：让接口封装类直接命中真实 endpoint，其余完全不变。
4. 加新维度（如模糊测试）：建一个 `tests/test_fuzz.py` + 加 `fuzz` marker。

每加一层，只在自己负责的地方加——这是「可工程化」与「堆砌 demo」的本质区别。
