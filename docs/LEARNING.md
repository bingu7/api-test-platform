# 学习路径：如何用这个仓库学接口自动化

目标：不是「会点运行 demo」，而是能说清每一层为什么这样设计，并能自己加一条新接口用例。

建议总时长：3～5 个晚上。每天只做一节 + 一个小实验。

---

## 第 0 天：跑通

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/ -v
python -m pytest tests/ -m smoke -v
```

观察：

- 总耗时是否在数秒内（若又回到 30s+，检查是否又写了 `localhost`）
- `test_framework` 是否通过（路径/Excel/TokenError）

---

## 第 1 天：配置与路径（`config/` + `utils/paths.py`）

**读**

1. `config/settings.py` — `Settings` 数据类、环境默认值、环境变量覆盖  
2. `utils/paths.py` — 为什么用 `PROJECT_ROOT` 而不是 `data/xxx.xlsx` 相对路径  

**实验**

```bash
# PowerShell —— 切记用 API_USERNAME，不要用 USERNAME（Windows 系统变量）
$env:API_USERNAME="admin"
$env:API_PASSWORD="wrong"
python -m pytest tests/test_framework.py::test_token_error_on_bad_password -v
Remove-Item Env:API_PASSWORD
```

**自问**

- `get_settings("no-such-env")` 为什么要抛错而不是静默用 dev？
- 为什么配置键叫 `API_USERNAME` 而不是 `USERNAME`？（提示：Windows 已占用）
- 若在 `tests/` 目录下执行 pytest，相对路径会怎样？绝对路径呢？

---

## 第 2 天：HttpClient 与 Token（`core/base_request.py` + `token_manager.py`）

**读**

1. `HttpClient.request(..., auth=True/False)`  
2. `TokenManager.get_token` 缓存与提前 60s 过期  
3. `TokenError` 与裸 `KeyError` 的差别  

**实验**

在 `tests/` 临时写一个用例（学完可删）：

```python
def test_auth_flag(api_client, raw_client):
    # 无 token 应 401
    r1 = raw_client.get("/api/user/profile", auth=False)
    assert r1.status_code == 401
    # 有 token 应 200
    r2 = api_client.get("/api/user/profile", auth=True)
    assert r2.status_code == 200
```

**自问**

- 为什么登录负向用例不能用默认 `auth=True`？
- Retry 为什么只对 5xx，不对 401？

---

## 第 3 天：Mock 与 Fixture（`core/mock_server.py` + `conftest.py`）

**读**

1. `MockServer`：随机端口、就绪探测、`base_url`/`auth_url`  
2. session 级 `mock_server` / `api_client` / `raw_client`  

**实验**

- 把 `mock_server` fixture 的 `scope` 改成 `function` 再跑全量，感受启动次数与耗时变化，然后改回 `session`。  
- 阅读 `/api/user/profile` 的 Bearer 校验逻辑。

**自问**

- 多个测试文件各自 `start_mock_server(5000)` 有什么问题？
- `port=0` / 系统分配端口解决了什么？

---

## 第 4 天：数据驱动与断言（`utils/excel_reader.py` + `assert_helpers.py` + Excel）

**读**

1. Excel 列约定与 `REQUIRED_COLUMNS`  
2. `filter_cases(endpoints=...)`  
3. `assert_case_response`  

**实验**

在 `data/test_cases.xlsx` 增加一行登录用例（例如错误用户名），再跑：

```bash
python -m pytest tests/test_login.py -v
```

**自问**

- 业务 code 与 HTTP status 为什么都要断言？
- 订单用例里对 `orders[0].keys()` 的结构断言解决了什么假绿问题？

---

## 第 5 天：自己加一条「新接口」

按正规流程扩展（不要只在一个文件里堆逻辑）：

1. **Mock**：在 `core/mock_server.py` 增加 `GET /api/health` → `{"code":0,"message":"ok"}`  
2. **用例**：`tests/test_health.py` 用 `raw_client` 断言 200 + code  
3. **（可选）Excel**：加一行数据驱动  
4. **标记**：给主路径加 `@pytest.mark.smoke`  
5. **报告**：

```bash
python -m pytest tests/ --alluredir=allure-results
allure serve allure-results
```

做完后你应能向面试官讲清：

> 配置 → 客户端 → Token → Mock/真实服务 → Fixture 注入 → 数据驱动 → 断言 → 报告

---

## 推荐阅读顺序（文件）

```
README.md
docs/LEARNING.md          ← 你在这里
config/settings.py
utils/paths.py
utils/logger.py
core/token_manager.py
core/base_request.py
core/mock_server.py
conftest.py
utils/excel_reader.py
utils/assert_helpers.py
tests/test_login.py
tests/test_user.py
tests/test_orders.py
tests/test_payment.py
tests/test_framework.py
```

---

## 反模式清单（项目里已避免，学习时别加回去）

| 反模式 | 正规做法 |
|--------|----------|
| 登录测试强制带 Bearer | `auth=False` / `raw_client` |
| 每文件起一个 Mock 固定 5000 端口 | session 级 + 随机端口 |
| `localhost` | `127.0.0.1` |
| Excel 相对 cwd | `data_file()` / 绝对路径 |
| Token 失败 `KeyError` | `TokenError` + 状态码/body |
| 全局 404 文案写成「用户未找到」 | 业务 404 vs 路由 404 分开 |
| README 写 Jenkins/邮件却没代码 | 仓库已提供 `Jenkinsfile` + `NOTIFY_EMAIL` 钩子，按文档配置即可 |
| 本机一套命令、CI 另一套 | 统一 `scripts/ci_test.sh|.bat` |

---

## 第 6 天：CI / Jenkins / 完整交付（扩展）

**读**

1. [FLOW.md](./FLOW.md) — 端到端流程图  
2. [JENKINS.md](./JENKINS.md) — 建任务与插件  
3. 根目录 `Jenkinsfile`、`scripts/ci_test.*`  

**实验**

```bat
scripts\ci_test.bat smoke
dir reports
dir allure-results
```

确认生成 `reports\junit.xml` 与 `allure-results\`。有 Allure CLI 时：`allure serve allure-results`。

**自问**

- 为什么 CI 不直接写一长串 `pytest` 在 Jenkinsfile 里，而要抽到 `scripts/`？
- smoke 与 full 分别适合什么门禁？

---

## 学完后可继续的方向

1. 对接真实测试环境（环境变量切换，mock 仅 dev 启用）  
2. JSON Schema 校验（`jsonschema`）  
3. 接口依赖：下单 → 查询订单号串联  
4. Allure 分类更细：`allure.epic` / 链接缺陷系统  
5. Jenkins 共享库 / 多分支 Pipeline  

每次只加一层，跑绿再提交。
