# 接口自动化测试平台

基于 **Python + Pytest + Requests + Flask Mock + Excel 数据驱动 + Allure + JSON Schema + 真实环境对接** 的面试级接口自动化框架。

> ❌ 不是点击运行 demo。  
> ✅ 能讲清每一层的设计原因，能自己加接口、加 Schema、加链路用例。

---

## 快速开始

```bash
# 1. 虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # Linux/macOS

# 2. 依赖
pip install -r requirements.txt

# 3. 本地 Mock（默认，零外网）
python -m pytest tests/ -v

# 4. 只跑冒烟
python -m pytest tests/ -v -m smoke

# 5. 真实环境（jsonplaceholder.typicode.com，需联网）
$env:TEST_ENV="test"
python -m pytest tests/ -v

# 6. CI 入口（与 Jenkins 相同）
scripts\ci_test.bat full
```

---

## 核心能力（面试叙述线）

```
配置层(config) → HTTP客户端(core) → Token(Mock) → 数据驱动(Excel) → 断言(assert_helpers)
                ↓                                          ↓
          Schema校验(jsonschema)                    边界/异常用例
                ↓                                          ↓
          内存数据库(MockDB)                         并发/性能
                ↓                                          ↓
          业务链路(workflow)                     真实环境(jsonplaceholder)
                ↓
         CI交付(JUnit + Allure + Jenkinsfile)
```

---

## 项目结构

```
api-test-platform/
├─ config/settings.py              # 多环境配置（dev/test/staging）
├─ core/
│  ├─ base_request.py              # HttpClient: Session+Retry+401自动重登
│  ├─ token_manager.py             # Token缓存+过期刷新
│  ├─ mock_server.py               # Flask Mock 服务（边界/DB/鉴权路由）
│  └─ mock_db.py                   # 内存数据库（订单CURD+线程安全）
├─ utils/
│  ├─ excel_reader.py              # Excel读取+列校验+过滤
│  ├─ assert_helpers.py            # 通用断言（HTTP/业务/Allure附件）
│  ├─ schema_validator.py          # JSON Schema 结构校验
│  ├─ paths.py / logger.py         # 路径常量+统一日志
├─ data/test_cases.xlsx             # Excel 数据驱动用例（12条）
├─ conftest.py                     # Fixture注入+环境感知+marker控制
├─ pytest.ini                       # 标记定义（smoke/slow/real_env）
├─ requirements.txt
├─ .env.example
├─ Jenkinsfile                     # 声明式流水线（参数化+Allure+邮件）
├─ .github/workflows/api-tests.yml  # GitHub Actions
├─ scripts/ci_test.sh / .bat       # CI 统一入口
├── Makefile
└── docs/
    ├── FLOW.md
    ├── JENKINS.md
    └── LEARNING.md
```

---

## 测试覆盖矩阵

| 测试文件 | 用例数 | 覆盖维度 |
|----------|--------|----------|
| `test_framework.py` | 6 | 框架自检：路径/Excel/配置/Token错误 |
| `test_login.py` | 5 | 登录：Excel 数据驱动 + raw_client |
| `test_user.py` | 2 | 用户：鉴权接口 + 无Token401 |
| `test_orders.py` | 7 | 订单+异常：数据驱动+结构断言+边界 |
| `test_payment.py` | 3 | 支付：DB校验+超时504 |
| `test_schema.py` | 4 | Schema：登录/用户/订单/错误响应结构 |
| `test_edge_cases.py` | 8 | 边界：空body/缺字段/大payload/500/Content-Type |
| `test_workflow.py` | 5 | 链路：登录→用户→下单→查单→支付→DB |
| `test_concurrency.py` | 3 | 并发：100批量登录/线程并发/DB并发写 |
| `test_real_env.py` | 25 | 真实环境：jsonplaceholder 6类资源+CRUD+性能 |
| **Total** | **68** | |

---

## 环境切换

```powershell
# dev（默认）— 全 Mock，零外网，5s 内跑完
python -m pytest tests/ -v

# test — 对接 jsonplaceholder.typicode.com（免费公开 API）
$env:TEST_ENV="test"
python -m pytest tests/ -v

# staging — 注入自定义 BASE_URL
$env:TEST_ENV="staging"
$env:BASE_URL="https://your-api.com"
python -m pytest tests/ -v
```

> dev 环境下 @pytest.mark.real_env 的用例自动 skip。

---

## 面试能回答的关键问题

| 问题 | 回答演示 |
|------|---------|
| 接口之间怎么串联 | `test_workflow.py`: 五步链路 + 并发 session 级 Token 共享 |
| 怎么保证数据真的落库了？ | `test_payment.py::test_payment_with_db_check`: API 返回 + DB 双校验 |
| amount 从数字变成字符串你能发现吗？ | `test_schema.py`: jsonschema + 类型检查 |
| 并发场景你怎么测？ | `test_concurrency.py`: 100 批次登录 + 20 线程并发写给 DB |
| 项目没有真实环境怎么验证？ | `TEST_ENV=test` 一键切 jsonplaceholder 免费 API |
| CI 怎么配的？ | `Jenkinsfile`: 参数化 + JUnit + Allure + 可选邮件 + artifacts |

---

## 核心约定

| 规则 | 说明 |
|------|------|
| Windows 用 `127.0.0.1` | 不要用 `localhost` |
| 登录用 `raw_client + auth=False` | 避免走了 Bearer 测不了原接口 |
| Excel 路径走 `utils/paths` | 不写死相对 cwd |
| `API_USERNAME` 不可 `USERNAME` | 避免 Windows 系统变量冲突 |
| 多环境切换：`TEST_ENV` | dev=Mock, test=jsonplaceholder, staging=自定义 |
| 提交前跑 `scripts/ci_test` | 与 CI/Jenkins 同入口 |

---

## Jenkins 一分钟

1. Pipeline → SCM → Script Path: `Jenkinsfile`
2. 参数选 `smoke` 或 `full`
3. 可选：环境变量 `NOTIFY_EMAIL` 启邮件

---

## 反模式清单（项目已杜绝）

| 反模式 | 正规做法 |
|--------|----------|
| 登录测试带 Bearer | `auth=False + raw_client` |
| 每文件起一个 Mock  | session 级复用 |
| `localhost` |`127.0.0.1` |
| Token 错误 KeyError | `TokenError` 错误信息 |
| 业务 404 vs 路由 404 混淆 | 分开定义 |
| 本机 CI 两套命令 | 统一 `scripts/ci_test` |

---

## 待扩展方向

- JSON Schema 全覆盖（所有端口）
- 真实服务本项目对接
- 数据库预写/清理 + 数据隔离
- Jenkins 共享库 / 标记 Pipeline

> 每个方向在现有分层基础上扩展即可，不需要重构。