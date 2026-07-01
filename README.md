# 接口自动化测试平台

基于 Python + Pytest + Requests 搭建的轻量级接口自动化测试框架。

## 特性

- 统一 HTTP 请求封装（会话管理、Token 自动续期、重试机制）
- 数据驱动测试（Excel/JSON 数据源）
- 多环境切换（dev / test / staging）
- Mock 服务集成
- Jenkins CI 集成 + 邮件通知
- Allure 可视化报告

## 快速开始

```bash
pip install -r requirements.txt

# 运行测试
python -m pytest tests/

# 指定环境
TEST_ENV=test python -m pytest tests/

# 生成 Allure 报告
python -m pytest tests/ --alluredir=allure-results
allure serve allure-results
```

## 项目结构

```
├── config/          # 环境配置
├── core/            # 核心封装（请求基类、Token管理、Mock）
├── data/            # 测试数据（Excel）
├── tests/           # 测试用例
├── utils/           # 工具类
├── conftest.py      # Pytest 全局 fixture
└── pytest.ini       # Pytest 配置
```
