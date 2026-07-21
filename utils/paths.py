"""项目路径常量：所有数据文件读取都应基于 PROJECT_ROOT，避免 cwd 依赖。"""
from pathlib import Path

# api-test-platform/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
ALLURE_RESULTS_DIR = PROJECT_ROOT / "allure-results"
REPORTS_DIR = PROJECT_ROOT / "reports"


def data_file(name: str) -> Path:
    """返回 data/ 下文件的绝对路径。"""
    return DATA_DIR / name
