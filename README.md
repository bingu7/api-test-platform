# 接口自动化测试平台

基于 **Python + Pytest + Requests + Flask Mock + Excel 数据驱动 + Allure** 的可学习型接口自动化框架。

目标：结构接近真实测开/QA 项目，用本地 Mock 完整走通：

**写用例 → 本地验证 → 同一 CI 脚本 → Jenkins / GitHub Actions → JUnit + Allure → 可选邮件**

---

## 特性

| 能力 | 说明 |
|------|------|
| HttpClient | Session、Retry、`auth=True/False` 分流 |
| TokenManager | 缓存 + 过期刷新 + `TokenError` 明确失败 |
| Mock 服务 | session 级共享、随机端口、就绪探测、简易鉴权 |
| 多环境配置 | `TEST_ENV` + `API_USERNAME`/`API_PASSWORD`（勿用 `USERNAME`） |
| 数据驱动 | Excel 绝对路径读取 + 列校验 |
| 断言封装 | HTTP / 业务 code / message / Allure 附件 |
| CI 入口 | `scripts/ci_test.sh` / `.bat`（本地与 Jenkins 同命令） |
| Jenkins | 根目录 `Jenkinsfile`：参数化 + JUnit + Allure + 可选邮件 |
| GitHub Actions | `.github/workflows/api-tests.yml` 复用同一脚本 |

---

## 快速开始

```bash
# 1. 虚拟环境（推荐）
python -m venv .venv
# Windows
.venv\Scripts\activate

# 2. 依赖
pip install -r requirements.txt

# 3. 跑全部
python -m pytest tests/ -v

# 4. 只跑冒烟
python -m pytest tests/ -v -m smoke

# 5. 与 Jenkins 相同的入口（推荐提交前执行）
scripts\ci_test.bat smoke
scripts\ci_test.bat full
# Git Bash / Linux:
# bash scripts/ci_test.sh full

# 6. 本地看 Allure（需 allure CLI）
allure serve allure-results
```

Windows 也可双击 `run_tests.bat`。

切换环境示例：

```powershell
$env:TEST_ENV="test"
# 对接真实服务时：
# $env:BASE_URL="https://..."
# $env:API_USERNAME="..."
# $env:API_PASSWORD="..."
python -m pytest tests/ -v
```

> 当前用例默认打 **本地 Mock**（session fixture 启动）。对接真实服务时注入 `BASE_URL` / `AUTH_URL` / `API_*`。

---

## 完整流程文档

| 文档 | 内容 |
|------|------|
| **[docs/FLOW.md](docs/FLOW.md)** | 端到端交付流程图 + 检查清单 |
| **[docs/JENKINS.md](docs/JENKINS.md)** | Jenkins 建任务、插件、邮件、排障 |
| **[docs/LEARNING.md](docs/LEARNING.md)** | 按天学习代码分层 |

---

## 项目结构

```
api-test-platform/
├── Jenkinsfile                 # Jenkins 声明式流水线
├── Makefile                    # install/smoke/full/ci-*（可选）
├── config/settings.py
├── core/                       # HttpClient / Token / Mock
├── data/test_cases.xlsx
├── tests/
├── utils/
├── scripts/
│   ├── ci_test.sh              # Linux/macOS/Git Bash CI 入口
│   └── ci_test.bat             # Windows CI 入口
├── reports/                    # junit.xml（gitignore 内容）
├── allure-results/             # Allure 原始结果
├── .github/workflows/api-tests.yml
├── conftest.py
├── pytest.ini
├── requirements.txt
├── .env.example
├── run_tests.bat
└── docs/
    ├── FLOW.md
    ├── JENKINS.md
    └── LEARNING.md
```

---

## 核心约定（必读）

1. **Windows 一律用 `127.0.0.1`**，不要用 `localhost`。
2. **登录/公开接口**用 `raw_client` + `auth=False`；**需登录接口**用 `api_client`。
3. **Excel 路径**走 `utils.paths`，不要写死相对 cwd。
4. **断言**优先 `utils.assert_helpers`。
5. 账号环境变量用 **`API_USERNAME` / `API_PASSWORD`**，不要用 `USERNAME`。
6. **提交前**跑一遍 `scripts/ci_test.*`，与 Jenkins 保持一致。

---

## Jenkins 一分钟

1. 新建 Pipeline 任务 → Pipeline script from SCM → Script Path: `Jenkinsfile`  
2. 构建参数选 `smoke` 或 `full`  
3. 可选：环境变量 `NOTIFY_EMAIL`  
4. 详情：[docs/JENKINS.md](docs/JENKINS.md)

---

## 未包含（刻意后续再加）

- 数据库校验、JSON Schema 全量库  
- 分布式并行压测  
- 真实 SMTP 服务器配置（仓库只提供钩子）

需要时在现有分层上扩展即可。
