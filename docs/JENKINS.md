# Jenkins 接入指南（学习用）

本仓库用 **Declarative Pipeline + 脚本入口**，本地和 Jenkins 跑同一条命令，避免「本机绿、CI 红且无法复现」。

---

## 你将学到什么

1. `Jenkinsfile` 声明式流水线结构（agent / stages / post）
2. 参数化构建（smoke / full、环境名）
3. JUnit 趋势 + Allure 报告
4. 可选邮件（`NOTIFY_EMAIL` + Email Extension）
5. Windows / Linux Agent 双脚本（`ci_test.bat` / `ci_test.sh`）

---

## 前置

| 项 | 说明 |
|----|------|
| Jenkins | 2.// 任意 LTS 即可 |
| Agent | 装好 **Python 3.10+**，能访问 Git |
| 推荐插件 | Pipeline、Git、JUnit、**Allure**、Timestamper、Email Extension（邮件可选） |
| Allure 命令行 | 可选；Jenkins Allure 插件可只吃 `allure-results/` |

---

## 本地先模拟 CI（强烈建议）

在项目根目录：

```bash
# Git Bash / Linux / macOS
bash scripts/ci_test.sh smoke
bash scripts/ci_test.sh full
```

```bat
REM Windows CMD
scripts\ci_test.bat smoke
scripts\ci_test.bat full
```

成功后应有：

- `reports/junit.xml`
- `allure-results/`（若干 json）

再在本机看报告（需安装 allure CLI）：

```bash
allure serve allure-results
```

---

## 创建 Pipeline 任务

1. **新建任务** → Pipeline  
2. **Pipeline definition** → *Pipeline script from SCM*  
3. SCM：你的 Git 地址；分支如 `*/main`  
4. Script Path：`Jenkinsfile`  
5. 保存  

首次构建前确认 Agent 标签与 `agent any` 匹配；若只有带标签节点，改成：

```groovy
agent { label 'python' }
```

---

## 构建参数

| 参数 | 含义 |
|------|------|
| `TEST_SUITE` | `smoke` 快返 / `full` 全量 |
| `TEST_ENV` | 写入环境变量，供 `config/settings.py` 读取 |
| `CLEAN_WORKSPACE` | 排障时勾选，清理后重新 checkout |

环境变量（Job 配置 → Environment / Credentials Binding）：

| 变量 | 说明 |
|------|------|
| `API_USERNAME` / `API_PASSWORD` | 测试账号（**不要**用 `USERNAME`） |
| `BASE_URL` / `AUTH_URL` | 对接真实服务时覆盖 |
| `NOTIFY_EMAIL` | 收件人；不设则跳过邮件 |

当前默认用例走 **本地 Mock**，不配账号也能绿；对接真实服务再注入凭据。

---

## 流水线阶段

```
Prepare → Test (scripts/ci_test.*) → Publish (JUnit + Allure + 归档)
                post: always junit / 邮件
```

失败时：打开构建 → **Test Result** 看 JUnit；**Allure Report** 看步骤附件；**Build Artifacts** 可下载原始 `allure-results`。

---

## 邮件（可选）

1. 安装 **Email Extension Plugin**  
2. 系统管理 → 配置 SMTP  
3. Job 环境变量：`NOTIFY_EMAIL=you@example.com`  
4. 成功/失败都会尝试 `emailext`；未装插件时只打日志，不拖垮构建  

---

## 常见问题

### 1. Windows Agent 报 bash 找不到

用的是 `bat scripts\\ci_test.bat`，不要强行 sh。若节点只有 Git Bash，也可改 `agent` 用 Unix 兼容环境。

### 2. Allure 步骤报错

插件未装时 Pipeline 会 catch 并继续，**artifacts 里仍有 allure-results**。装好插件后重新构建即可出链接。

### 3. `USERNAME` 登录失败

Windows 系统变量 `USERNAME` 是系统用户名。本框架只用 **`API_USERNAME`**。详见 `docs/LEARNING.md`。

### 4. 权限：`ci_test.sh` 无法执行

Pipeline 里已有 `chmod +x`；若 SCM 丢弃可执行位，保持该 step 即可。

### 5. 与 GitHub Actions 的关系

本仓优先 Jenkins（测开/甲方常见）。若以后要 GH Actions，可复用 `scripts/ci_test.sh`，不必改 pytest 本身。

---

## 建议练习

1. 故意改坏一条断言 → 看 Jenkins **UNSTABLE/FAILURE** 与 JUnit 趋势  
2. 只跑 `smoke` 与 `full` 对比时长  
3. 配一个 `NOTIFY_EMAIL` 测邮件正文链接  
4. 阅读 `Jenkinsfile` 的 `post` 与 `notifyEmail`，试着加「构建描述 setBuildDescription」  

对应学习主线见 [LEARNING.md](./LEARNING.md) 扩展节。
