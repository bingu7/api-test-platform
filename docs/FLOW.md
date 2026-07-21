# 完整交付流程（端到端）

把接口自动化当成「可交付工程」，而不是本地点一下的 demo。

```
  ┌─────────────┐     ┌──────────────┐     ┌────────────────┐
  │  写用例/数据  │ ──► │  本地 pytest  │ ──► │  scripts/ci_*  │
  │  Excel/代码  │     │  smoke/full  │     │  (与 CI 同入口) │
  └─────────────┘     └──────────────┘     └────────┬───────┘
                                                    │
                     ┌──────────────────────────────┼──────────────────────────┐
                     ▼                              ▼                          ▼
              ┌────────────┐               ┌──────────────┐            ┌─────────────┐
              │  Jenkins   │               │ GitHub Actions│            │  本机模拟 CI │
              │ Jenkinsfile│               │ workflow     │            │  ci_test.*  │
              └─────┬──────┘               └──────┬───────┘            └──────┬──────┘
                    │                             │                           │
                    └─────────────┬───────────────┴─────────────┬─────────────┘
                                  ▼                             ▼
                           reports/junit.xml              allure-results/
                                  │                             │
                                  ▼                             ▼
                           测试趋势 / 门禁                  Allure 报告
                                  │                             │
                                  └──────────┬──────────────────┘
                                             ▼
                                    可选邮件 NOTIFY_EMAIL
```

---

## 1. 开发阶段（你每天做的事）

| 步骤 | 动作 | 对应路径 |
|------|------|----------|
| 1 | 改配置 / 读环境变量 | `config/settings.py`、`.env.example` |
| 2 | 封装请求 / Token / Mock | `core/` |
| 3 | 写或改 Excel 数据 | `data/test_cases.xlsx` |
| 4 | 写测试 | `tests/`，注入 `api_client` / `raw_client` |
| 5 | 本地快验 | `pytest -m smoke` |
| 6 | 本地全量 | `pytest` 或 `scripts/ci_test.bat full` |

原则：

- 登录用 `raw_client` + `auth=False`
- 业务鉴权用 `api_client`
- 断言优先 `utils/assert_helpers.py`

---

## 2. 本地「模拟 CI」（提交前必做）

与 Jenkins 同一套入口，避免环境漂移：

```bat
scripts\ci_test.bat smoke
scripts\ci_test.bat full
```

```bash
bash scripts/ci_test.sh smoke
bash scripts/ci_test.sh full
```

产物：

| 路径 | 用途 |
|------|------|
| `reports/junit.xml` | Jenkins JUnit / 趋势图 |
| `allure-results/` | Allure 原始结果 |

本机看 Allure（需安装 [Allure CLI](https://docs.qameta.io/allure/)）：

```bash
allure serve allure-results
```

---

## 3. 持续集成

### Jenkins（主推，测开常见）

见 **[JENKINS.md](./JENKINS.md)**。

要点：

- 流水线文件：根目录 `Jenkinsfile`
- 参数：`TEST_SUITE` = smoke|full，`TEST_ENV` = dev|test|staging
- 阶段：Prepare → Test → Publish（JUnit + Allure + 归档）
- 邮件：环境变量 `NOTIFY_EMAIL`（可选）

### GitHub Actions（仓库已带）

- 文件：`.github/workflows/api-tests.yml`
- 同样调用 `scripts/ci_test.sh`
- PR 默认 smoke；`workflow_dispatch` 可选 full
- Artifact：junit + allure-results

---

## 4. 报告与门禁

| 门禁 | 含义 |
|------|------|
| pytest exit code ≠ 0 | 构建失败 / UNSTABLE（视 Jenkins 配置） |
| JUnit | 历史通过率、失败用例定位 |
| Allure | 步骤、附件、分级（blocker/critical） |
| smoke 先于 full | 可在 Jenkins 只跑 smoke 做合并门禁 |

推荐策略：

- **合并前 / 夜间**：`full`
- **每次提交 / PR**：`smoke`

---

## 5. 通知（可选）

1. Jenkins 安装 Email Extension，配置 SMTP  
2. Job 增加环境变量 `NOTIFY_EMAIL`  
3. 成功 / 失败 / unstable 由 `Jenkinsfile` 的 `notifyEmail` 发送  

未配置时只打日志，**不阻断构建**。

---

## 6. 对接真实服务时的流程差量

默认：session fixture 起 **本地 Mock**，零外网。

切真实环境时：

1. Jenkins / 本机注入 `BASE_URL`、`AUTH_URL`、`API_USERNAME`、`API_PASSWORD`  
2. `TEST_ENV=test` 或 `staging`  
3. 后续可把 `mock_server` 改成「仅 `TEST_ENV=dev` 启用」（进阶优化）  

**切勿**使用环境变量名 `USERNAME`（Windows 系统占用）。

---

## 7. 一页检查清单（交付自检）

- [ ] `pytest tests/ -q` 全绿  
- [ ] `scripts/ci_test.bat smoke` 产出 junit + allure-results  
- [ ] README / LEARNING 与真实结构一致  
- [ ] Jenkinsfile 能在至少一种 Agent（Win 或 Linux）跑通  
- [ ] 密钥不进仓库（只用 `.env` / Jenkins 凭据）  
- [ ] 新增接口遵循：Mock（可选）→ 客户端 → 用例 → Excel（可选）→ smoke 标记  

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [LEARNING.md](./LEARNING.md) | 按天学代码分层 |
| [JENKINS.md](./JENKINS.md) | Jenkins 安装与排障 |
| [../README.md](../README.md) | 快速开始 |
| [../Jenkinsfile](../Jenkinsfile) | 流水线源码 |
