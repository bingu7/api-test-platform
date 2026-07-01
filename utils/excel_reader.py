import json
import pandas as pd


def read_test_cases(file_path: str) -> list:
    """读取 Excel 测试数据，返回参数字典列表"""
    df = pd.read_excel(file_path, dtype=str)
    cases = []
    for _, row in df.iterrows():
        case = {
            "name": row["case_name"],
            "endpoint": row["endpoint"],
            "method": row["method"],
            "body": json.loads(row["body"]) if pd.notna(row.get("body")) else None,
            "expected_status": int(row["expected_status"]),
            "expected_msg": row.get("expected_msg"),
        }
        cases.append(case)
    return cases