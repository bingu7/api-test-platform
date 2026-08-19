# 接口自动化测试平台

基于 **Python + Pytest + Requests + FastAPI 真实后端 + Flask Mock + Excel 数据驱动 + Allure + JSON Schema + JWT 鉴权 + SQLite 落库校验 + 接口安全 / 性能 / 契约测试 + Jenkins/GH Actions CI** 的完整接口自动化框架。

> ❌ 不是点击运行的 demo。
> ✅ 一套能讲清每一层为什么这样设计、能拿来测真实 REST API、能直接套用到上线上线项目的工程骨架。

---

## 三种被测系统，一个测试框架

| 环境 `TEST_ENV` | 被测系统 | 用途 | 启动方式 |
|------|---------|------|---------|
| `dev`（默认） | Flask Mock（本地假数据） | 零外网，秒级回放 | conftest 自动起 |
| **`real`** | **FastAPI 真实后端**（电商：用户/商品/订单/支付 + JWT + SQLite） | **学测真实 REST API + 全维度测试** | **conftest 子进程起 uvicorn** |
| `test` | jsonplaceholder.typicode.com | 公开免费 API 联调 | 直连 |
| `staging` | 自定义 `BASE_URL` | 对接你的真实服务 | 直连 |

三个被测系统互不相同，但 **同一份测试代码**——靠环境 marker 分发（`mock_only` / `backend` / `real_env`）。

---

## 快速开始

```bash
# 1. 虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # Linux/macOS

# 2. 装依赖（测试框架）
pip install -r requirements.txt
#    real 环境（测真实后端）还需装后端依赖：
pip install -r apps/backend/requirements.txt

# 3. 跑 Flask Mock 用例（默认 dev 环境，零外网）
python -m pytest tests/ -v

# 4. 跑真实后端用例（real 环境，全维度）
TEST_ENV=real python -m pytest tests/ -v
# Windows PowerShell:  $env:TEST_ENV="real"; python -m pytest tests/ -v

# 5. 只跑冒烟（任环境）
python -m pytest tests/ -v -m smoke
TEST_ENV=real python -m pytest tests/ -v -m smoke

# 6. 单独跑某维度（real 环境）
TEST_ENV=real python -m pytest tests/ -v -m security       # 安全
TEST_ENV=real python -m pytest tests/ -v -m performance    # 性能
TEST_ENV=real python -m pytest tests/ -v -m contract       # 契约
TEST_ENV=real python -m pytest tests/ -v -m db_check       # DB 落库

# 7. 前台手起后端（看 Swagger UI / 调试用）
make backend        # 或 scripts\start_backend.bat
#   Swagger UI:  http://127.0.0.1:8000/docs
#   OpenAPI 规范: http://127.0.0.1:8000/openapi.json

# 8. CI 入口（与 Jenkins/GH Actions 相同）
scripts\ci_test.bat dev     # 或 real / test，可选 smoke / full
```

---

## 完整分层架构

```
    配置层(config)        多环境配置（dev/real/test/staging）
         │
    基础设施(core)        HttpClient(Session+Retry+401自动重登)/TokenManager
         │               MockServer(Flask)/BackendServer(uvicorn子进程)
         │
    被测系统              ┌── apps/backend (FastAPI+JWT+SQLite) —— 真实 REST
    (SUT)                └── core/mock_server (Flask)           —— 本地 Mock
         │
    接口封装(apis)        PO 模式：AuthAPI / ProductAPI / OrderAPI / PaymentAPI
         │               「怎么调接口」只写一次，测试只写「调 + 断言」
         │
    数据层(data)          Excel 数据驱动 + Builder 模式构造 + 随机工厂
         │
    工具层(utils)         断言助手 / Schema 校验 / Excel 读取 / DB 白盒助手 / 日志
         │
    测试用例(tests)       正负向 / 数据驱动 / Schema / 链路 / 并发
         │               ── 后端专属 ── DB落库 / 安全 / 性能 / 契约 / 数据准备
         │
    CI/CD                scripts/ci_test.* + Jenkinsfile + .github/workflows
         │               └─ JUnit + Allure + 邮件 + artifacts
```

---

## 项目结构

```
api-test-platform/
├─ apps/backend/                 # ① 真实被测后端 (FastAPI + SQLAlchemy + JWT)
│  ├─ main.py                    #   FastAPI app + lifespan（启动建表灌种子）
│  ├─ database.py                #   async SQLAlchemy + SQLite
│  ├─ models.py                  #   ORM: User/Product/Order/Payment
│  ├─ schemas.py                 #   Pydantic 请求/响应模型 (422 校验源)
│  ├─ auth.py                    #   PBKDF2 哈希 + JWT 签发/校验
│  ├─ deps.py                    #   依赖注入: get_current_user / require_admin
│  ├─ routers/                   #   auth/products/orders/payment
│  ├─ seed.py                    #   初始演示数据 (admin/tester/3 商品/1 订单)
│  └─ requirements.txt           #   后端独立依赖
│
├─ apis/                          # ② 接口封装层 (PO 模式)
│  ├─ auth_api.py  product_api.py  order_api.py  payment_api.py
│
├─ core/                          # ③ 基础设施
│  ├─ base_request.py             #   HttpClient: Session+Retry+401重登+PATCH
│  ├─ token_manager.py            #   Token 缓存 + 过期刷新
│  ├─ mock_server.py  mock_db.py  #   Flask Mock (dev 环境)
│  └─ backend_server.py           #   BackendServer: uvicorn 子进程启停
│
├─ data/                          # ④ 数据层
│  ├─ test_cases.xlsx             #   Mock 用例 (12 条)
│  ├─ backend_cases.xlsx          #   后端用例 (15 条)
│  ├─ builders.py                 #   Builder 模式构造器
│  └─ factories.py                #   随机数据工厂 (零依赖)
│
├─ utils/                         # ⑤ 工具层
│  ├─ assert_helpers.py           #   assert_status/business/json_path/response_time
│  ├─ schema_validator.py         #   JSON Schema 校验
│  ├─ excel_reader.py             #   Excel 读取 + 列校验 + 过滤
│  ├─ db_helper.py                #   白盒直连 SQLite 断言 (落库校验)
│  ├─ logger.py  paths.py
│
├─ tests/                         # ⑥ 测试用例 (见下表)
├─ scripts/                       # ⑦ 脚本
│  ├─ ci_test.sh  ci_test.bat     #   CI 统一入口
│  ├─ start_backend.sh/.bat       #   前台起后端 (调试)
│  └─ perf_test.py                #   压测脚本
│
├─ config/settings.py             # ⑧ 多环境配置
├─ conftest.py  pytest.ini        # ⑨ fixture 注入 + marker + 环境过滤
├─ Jenkinsfile  .github/workflows/api-tests.yml    # CI 流水线
└─ docs/  README.md  .env.example  Makefile  requirements.txt
```

---

## 测试维度与用例矩阵

| 测试文件 | 环境 | 维度 | 覆盖 |
|----------|------|------|------|
| `test_framework.py` | dev | 自检 | 路径/Excel/配置/Token |
| `test_login.py` | dev | 数据驱动 | 登录正负向（Excel） |
| `test_user.py` | dev | 鉴权 | 取用户/无Token |
| `test_orders.py` | dev | 数据驱动 | 订单/异常/边界（Excel） |
| `test_payment.py` | dev | 双校验 | 支付+DB校验/超时 |
| `test_schema.py` | dev | Schema | 登录/用户/订单/错误结构 |
| `test_edge_cases.py` | dev | 边界 | 空/缺字段/大payload/500 |
| `test_workflow.py` | dev | 链路 | 登录→用户→下单→查→支付 |
| `test_concurrency.py` | dev | 并发 | 批量登录/线程/DB并发 |
| `test_real_env.py` | test | 公开API | jsonplaceholder CRUD |
| **`test_auth_api.py`** | **real** | **PO** | 注册/登录/me 正负向 |
| **`test_product_api.py`** | **real** | **PO+权限** | 商品 CRUD + 401/403 隔离 |
| **`test_order_api.py`** | **real** | **PO+边界** | 下单/查/取消/重复/422 |
| **`test_payment_api.py`** | **real** | **PO+幂等** | 支付/退款/幂等 |
| **`test_db_verification.py`** | **real** | **DB落库** | 注册/订单/支付 落库 + 幂等 |
| **`test_security.py`** | **real** | **安全** | 401/伪造/IDOR/越权/SQL注入/泄漏 |
| **`test_performance.py`** | **real** | **性能** | 基准时延/P95/并发吞吐 |
| **`test_contract.py`** | **real** | **契约** | OpenAPI 规范/响应结构 |
| **`test_data_preparation.py`** | **real** | **数据层** | Builder/Factory/清理 |

合计 **约 140 用例**（dev 42 + real 71 + test 25 + 跨环境共享 fixture）。

---

## 核心能力（面试叙述线）

```
配置层(config) → 客户端(core) → 被测系统(real后端/mock) → 接口封装(apis)
       ↓                                       ↓                  ↓
  Token(JWT/Mock)                   数据驱动(Excel+Builder)     断言(assert_helpers)
       ↓                                       ↓                  ↓
 Schema校验(jsonschema)              Builder/Factory 造数据    JSONPath/响应时间
       ↓                                       ↓                  ↓
 内存DB+真实SQLite                        边界/异常用例         DB 白盒落库校验
       ↓                                       ↓                  ↓
 业务链路(workflow)                     并发/性能(P95/QPS)      安全(IDOR/鉴权/SQL)
       ↓                                       ↓                  ↓
 契约测试(OpenAPI)                       真实环境(jsonplaceholder)  CI交付
       ↓                                                ↓
   JUnit + Allure                                     Jenkins/GH Actions
```

---

## 环境切换与 marker

| marker | 含义 | 运行环境 |
|--------|------|---------|
| `mock_only` | Flask Mock 业务用例 | dev |
| `backend` | FastAPI 真实后端用例 | real |
| `real_env` | jsonplaceholder 公开 API | test/staging |
| `smoke` | 冒烟核心路径 | 全环境 |
| `slow` | 较慢用例 | 全环境 |
| `security` `performance` `contract` `db_check` | 维度标记 | real |

`conftest.py` 的 `pytest_collection_modifyitems` 按 `TEST_ENV` 自动跳过不相干用例——你不会在 dev 跑后端用例，也不会在 real 跑 jsonplaceholder。

---

## 面试能回答的关键问题

| 问题 | 你指着哪个文件回答 |
|------|-------------------|
| 接口之间怎么串联 | `tests/test_workflow.py`：登录→用户→下单→查→支付（Mock）+ `test_auth_api.py` 的 login-then-me（后端） |
| 怎么保证数据真的落库了 | `test_db_verification.py`：接口返回 + DB 白盒直查（`utils/db_helper.py`） |
| 数据怎么准备、怎么隔离 | `data/builders.py` + `factories.py` + 测试后清理 |
| 接口安全怎么测 | `test_security.py`：401/伪造/IDOR/越权/SQL注入/泄露 |
| 性能怎么测 | `test_performance.py` + `scripts/perf_test.py`：P95/QPS/吞吐 |
| 契约怎么保证不漂移 | `test_contract.py`：拉 OpenAPI /openapi.json 逐端点校验 |
| 接口对象怎么封装 | `apis/` PO 模式：一行调方法、测试只写断言 |
| 多环境怎么切 | `TEST_ENV=dev|real|test|staging`，`conftest.py` 自动起对被测系统 |
| CI 怎么配 | `Jenkinsfile` + `.github/workflows/api-tests.yml` 跑同一 `scripts/ci_test.*` |

---

## 推荐学习路线

按天学，每天一节 + 一个小实验，完整路径见 **[docs/LEARNING.md](docs/LEARNING.md)**：
1. 跑通两个环境
2. 配置与路径
3. HttpClient 与 Token
4. 真实后端怎么写（apps/backend）
5. 接口封装层 PO 模式
6. 数据驱动 + 断言
7. Mock 与 fixture
8. DB 落库校验
9. 安全 / 性能 / 契约测试
10. CI/CD 完整交付

学完后能讲清：配置 → 客户端 → 被测系统 → 接口封装 → 数据层 → DB校验 → 断言 → 报告 → CI 全链路。

---

## 核心约定

| 规则 | 说明 |
|------|------|
| Windows 用 `127.0.0.1` | 不要用 `localhost`（解析慢） |
| 登录用 `raw_client + auth=False` | 避免走了 Bearer 测不了原接口 |
| `API_USERNAME` 不可 `USERNAME` | 避免 Windows 系统变量冲突 |
| Excel 路径走 `utils/paths` | 不写死相对 cwd |
| 后端 DB 每次启动清空重建 | `lifespan` 调 `reset_and_seed`，保证测试隔离 |
| 多用例随机账号 | `factories.fake_*()` / `AuthAPI.random_credential()` 避免撞库 |
| 提交前跑 `scripts/ci_test` | 与 CI/Jenkins 同入口 |

---

## 文档导航

| 文档 | 内容 |
|------|------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 分层详解——为什么这样设计（主读） |
| [docs/BACKEND.md](docs/BACKEND.md) | 被测后端怎么跑、怎么建表、怎么看 OpenAPI |
| [docs/LEARNING.md](docs/LEARNING.md) | 10 天学习路径 |
| [docs/FLOW.md]((docs/FLOW.md)) | 端到端交付流程图 |
| [docs/JENKINS.md](docs/JENKINS.md) | Jenkins 安装与排障 |

---

## 待扩展方向

- 接入真实第三方服务（替换 jsonplaceholder）
- Allure 接入缺陷系统链接、更细分类
- 后端加 Alembic 做迁移（演示用 reset 已够）
- 性能用 locust 替换 perf_test.py 做分布式压测
- 契约用 schemathesis 全自动 fuzz（现用手写覆盖已够清晰）

> 每个方向基于现有分层扩展即可，不需要重构。
