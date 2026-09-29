# 完整交付流程（端到端）

把接口自动化当成「可交付工程」，而不是本地点一下的 demo。

```
  ┌─────────────┐     ┌──────────────┐     ┌────────────────────┐
  │  写用例/数据  │ ──► │  本地 pytest  │ ──► │  scripts/ci_test.* │
  │  Excel/代码  │     │  real / dev   │     │  (与 CI 同入口)   │
  └─────────────┘     └──────────────┘     └────────┬───────────┘
                                                    │
        ┌───────────────────────────────────────────┼──────────────────────────┐
        ▼                                           ▼                          ▼
  ┌─────────────┐                            ┌──────────────┐            ┌─────────────┐
  │   Jenkins   │                            │ GitHub Actions │          │  本机模拟 CI │
  │  Jenkinsfile│                            │   workflow   │           │  ci_test.*  │
  │  TEST_ENV=  │                            │  matrix 2 env│           │             │
  └─────┬───────┘                            └──────┬───────┘            └──────┬──────┘
        │                                           │                           │
        │       real env 后端由 conftest 自动起 uvicorn 子进程              │
        │      （apps/backend/，无需 Jenkins 额外配）                       │
        └──────────────────┬─────────────────────────┴───────────┬────────────┘
                           ▼                                       ▼
                    reports/junit.xml                       allure-results/
                           │                                       │
                           ▼                                       ▼
                    测试趋势 / 门禁                            Allure 报告
                           │                                       │
                           └────────────────┬──────────────────────┘
                                            ▼
                                   可选邮件 NOTIFY_EMAIL
```

---

## 1. 开发阶段（每天做的事）

| 步骤 | 动作 | 对应路径 |
|------|------|----------|
| 1 | 改配置 / 环境变量 | `config/settings.py`、`.env.example` |
| 2 | 封装请求 / Token / 起被测 | `core/`、`apps/backend/` |
| 3 | 接口封装（PO） | `apis/`（接口变了只改这里） |
| 4 | 写或改数据 | `data/`（Excel / Builder / Factory） |
| 5 | 写测试 | `tests/`，按 marker 注入对应 fixture |
| 6 | 本地快验 | `pytest -m smoke`（dev / real） |
| 7 | 本地全量 | `pytest` 或 `TEST_ENV=real pytest` |
| 8 | 提交前模拟 CI | `scripts/ci_test.*`（dev / real / smoke / full） |

原则：

- 登录用 `raw_client` + `auth=False`
- 业务鉴权用 `api_client`
- 接口调用走 `apis/`（PO 模式），不在测试里写 raw URL
- 断言优先 `utils/assert_helpers.py`
- DB 落库校验优先 `utils/db_helper.py`

---

## 2. 本地「模拟 CI」（提交前必做）

与 Jenkins / GH Actions 同一套入口——这是「本机绿、CI 绿一致性」的关键。

```bash
# 任环境：
bash scripts/ci_test.sh full                  # 或 smoke
TEST_ENV=real bash scripts/ci_test.sh full    # 强制 real env

# Windows：
scripts\ci_test.bat full
```

CI 脚本会自动装两份依赖（`requirements.txt` + `apps/backend/requirements.txt`），保证 `TEST_ENV=real` 时后端能起。

产物：

| 路径 | 用途 |
|------|------|
| `reports/junit.xml` | Jenkins JUnit / 趋势图 |
| `allure-results/` | Allure 原始结果 |

本机看 Allure（需装 [Allure CLI](https://docs.qameta.io/allure/)）：

```bash
allure serve allure-results
```

---

## 3. 持续集成

### Jenkins（主推，测开常见）

见 **[JENKINS.md](./JENKINS.md)**。`TEST_ENV` 参数现在可选 `dev/real/test/staging`——选 `real` 时后端由 conftest 自动起，无需 Jenkins 配额外的进程管理步骤。

### GitHub Actions（仓库已带）

- 文件：`.github/workflows/api-tests.yml`
- matrix 跑两个 env：`dev`（Mock）+ `real`（后端）——两套都验证 CI 不红
- PR 默认 smoke；`workflow_dispatch` 可选 full
- Artifact：按 env 分桶上传 `junit-{env}` / `allure-results-{env}`

---

## 4. 报告与门禁

| 门禁 | 含义 |
|------|------|
| pytest exit code ≠ 0 | 构建失败 / UNSTABLE（视 Jenkins 配置） |
| JUnit | 历史通过率、失败用例定位 |
| Allure | 步骤、附件、分级（blocker/critical）+ 标记维度（security/performance/...） |
| smoke 先于 full | 可在 Jenkins 只跑 smoke 做合并门禁 |
| real / dev 双跑 | 上线前确认两套被测系统都绿 |

推荐策略：

- **合并前 / 夜间**：`full`（dev + real 都跑）
- **每次提交 / PR**：`smoke`

---

## 5. 通知（可选）

1. Jenkins 装 Email Extension，配 SMTP
2. Job 加 `NOTIFY_EMAIL=you@example.com`
3. 成功 / 失败 / unstable 由 `Jenkinsfile` 的 `notifyEmail` 发送

未配置时只打日志，**不阻断构建**。

---

## 6. 对接真实服务时的流程差量

| 场景 | 做法 |
|------|------|
| 测本地 FastAPI 后端 | `TEST_ENV=real`，conftest 自动起后端 |
| 测 jsonplaceholder 公开免费 API | `TEST_ENV=test` |
| 接你自己的真实后端 | 注入 `BASE_URL` / `AUTH_URL` / `API_USERNAME` / `API_PASSWORD`，`TEST_ENV=staging` |
| 改测另一套公开 API | 加 `_DEFAULTS["prod_open"]`，加 `real_env` marker 用例 |

**切勿**使用环境变量名 `USERNAME`（Windows 系统占用）。

---

## 7. 一页检查清单（交付自检）

- [ ] `pytest tests/` 全绿（dev）
- [ ] `TEST_ENV=real pytest tests/` 全绿（real）
- [ ] `scripts/ci_test.bat full` 产出 junit + allure-results
- [ ] README / ARCHITECTURE / LEARNING 与真实结构一致
- [ ] Jenkinsfile 能在至少一种 Agent（Win 或 Linux）跑通
- [ ] 密钥不进仓库（只用 `.env` / Jenkins 凭据）
- [ ] 新增接口遵循：后端（real）→ apis PO → 测试 → Builder/Excel → smoke → 对应 marker

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 每层为什么这样设计（主读） |
| [BACKEND.md](./BACKEND.md) | 被测后端怎么跑 / 接口一览 |
| [LEARNING.md](./LEARNING.md) | 按天学（10 天版） |
| [JENKINS.md](./JENKINS.md) | Jenkins 安装与排障 |
| [../README.md](../README.md) | 快速开始与矩阵 |
| [../Jenkinsfile](../Jenkinsfile) | 流水线源码 |
