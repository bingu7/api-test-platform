# 被测后端（apps/backend/）使用指南

这是项目的**真实被测系统**——一套 FastAPI + SQLite + JWT 的小型电商后端。不是真实的业务后端那么复杂，但**足够覆盖接口自动化测试里所有该测的维度**。

---

## 1. 三种跑法

### A) 前台手动起（调试、看 Swagger）

```bash
# Windows
scripts\start_backend.bat

# 或 Makefile
make backend

# 或直接（任意平台）
python -m uvicorn apps.backend.main:app --reload --port 8000
```

起来之后浏览器打开：

- **Swagger UI（交互调试接口）**：http://127.0.0.1:8000/docs
- **ReDoc（更可读的文档）**：http://127.0.0.1:8000/redoc
- **OpenAPI 规范 JSON**：http://127.0.0.1:8000/openapi.json
- **健康检查**：http://127.0.0.1:8000/health

在 Swagger UI 里点「Authorize」按钮、贴一个登录拿的 JWT，能直接在网页上调鉴权接口。

### B) 测试里 conftest 自动起

`TEST_ENV=real` 运行 pytest 时，`conftest.py` 的 `backend_server` fixture 会自动用子进程起 uvicorn、等就绪、测完关。你不用手动起。

```bash
TEST_ENV=real python -m pytest tests/ -v
```

### C) 不跑它（dev 环境）

`TEST_ENV=dev` 时测 Flask Mock，后端代码不跑、不依赖 FastAPI——脱离后端也能学习基础接口测试。

---

## 2. 数据库

- 文件：`apps/backend/dev.db`（SQLite）
- 每次后端启动 → `lifespan` 调用 `reset_and_seed()` → 清表 + 建表 + 灌种子
- 种子数据（见 `seed.py`）：
  - 用户：`admin`（admin/admin123，管理员）/`tester`（tester/tester123，普通用户）
  - 3 个商品（商品A/B/C）
  - 1 个种子订单 `SEED_ORD_001`（pending，归属 tester）

**测试隔离原则**：每次测试 session 启动 = 全新 DB。所以你的测试不必担心上次残留数据。

---

## 3. 接口一览

| 模块 | 方法 | 路径 | 鉴权 | 用途 |
|------|------|------|------|------|
| 健康 | GET | `/health` | 无 | 探活（conftest 就绪用） |
| 鉴权 | POST | `/api/auth/register` | 无 | 注册 |
| 鉴权 | POST | `/api/auth/login` | 无 | 登录拿 JWT |
| 鉴权 | GET | `/api/auth/me` | Bearer | 当前用户信息 |
| 商品 | GET | `/api/products` | 无 | 列表 |
| 商品 | GET | `/api/products/{id}` | 无 | 详情 |
| 商品 | POST | `/api/products` | admin | 新建 |
| 商品 | PUT | `/api/products/{id}` | admin | 更新 |
| 商品 | DELETE | `/api/products/{id}` | admin | 删除 |
| 订单 | GET | `/api/orders` | Bearer | 我的订单列表 |
| 订单 | POST | `/api/orders` | Bearer | 下单 |
| 订单 | GET | `/api/orders/{order_id}` | Bearer | 详情（仅本人） |
| 订单 | PUT | `/api/orders/{order_id}/cancel` | Bearer | 取消（仅本人） |
| 支付 | POST | `/api/payment/pay` | Bearer | 支付（幂等） |
| 支付 | POST | `/api/payment/refund` | Bearer | 退款 |
| 支付 | GET | `/api/payment/status/{order_id}` | Bearer | 查支付记录 |

状态码语义：

- `200` 成功 / `201` 新建 / `204` 删除
- `400` 业务校验失败（重复/状态不对）
- `401` 未鉴权 / token 无效 / 过期
- `403` 越权（IDOR / 权限不足）
- `404` 资源不存在
- `422` Pydantic 字段校验失败（必填/类型/长度）
- `500` 后端异常（不该出现）

---

## 4. 关键设计点（接口测试的「考点」）

### IDOR（越权）防护 — `routers/orders.py`

查/取消订单时校验 `order.user_id == current_user.id`，否则 403。对应测试 `test_security.py::TestIDOR`。

### 幂等支付 — `routers/payment.py`

同一 `idempotency_key` 第二次 pay 直接返回首次记录，不重复扣款。对应测试 `test_payment_api.py::test_idempotent_pay` + DB 校验 `test_db_verification.py::TestDbIdempotency`。

### 用户枚举防护 — `routers/auth.py`

登录失败统一返回「用户名或密码错误」，不区分用户名是否存在。对应测试 `test_security.py::test_login_wrong_password`（断言两种失败文案一致）。

### 权限隔离 — `deps.py`

`get_current_user` 解 JWT；`require_admin` 在其上加 role 检查。admin 接口对普通用户 → 403、对无 token → 401。

### SQL 注入天然防

所有查询走 SQLAlchemy 参数化（`select(User).where(User.username == ...)`）——不是字符串拼接，注入 payload 不会击穿 DB。对应测试 `test_security.py::TestSQLInjection`。

---

## 5. 常见问题

**Q：后端起不来、报端口冲突？**  
A：conftest 用系统分配空闲端口，不会冲突。手起时换 `--port 8001`。

**Q：DB 文件哪里去了？**  
A：每次 BackendServer 启动前会删 `apps/backend/dev.db`，让 lifespan 重建。这是设计——保证测试隔离。

**Q：改了后端代码怎么让它生效？**  
A：手动起的 `--reload` 模式自动热更；conftest 起的重启 pytest 即可。

**Q：能不依赖 SQLite 改成 Postgres 吗？**  
A：能——改 `database.py` 的 `create_async_engine` URL 和 `aiosqlite` → `asyncpg`，其余不动（SQLAlchemy 抽象了 dialect）。

**Q：后端的 OpenAPI 契约哪里看？**  
A：`http://127.0.0.1:8000/openapi.json`——契约测试 `test_contract.py` 就是拉它做断言源。
