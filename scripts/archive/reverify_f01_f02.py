"""复测脚本：F-02 用户枚举（不限流 server 8900）。"""
import json
import requests

BASE = "http://127.0.0.1:8900"
results = {}

# F-02: 用户枚举 — 不存在用户应 401（不再404），消息与密码错误一致
r1 = requests.post(f"{BASE}/api/login", json={"username": "notexist", "password": "x"}, timeout=5)
r2 = requests.post(f"{BASE}/api/login", json={"username": "admin", "password": "wrong"}, timeout=5)
m1 = r1.json().get("message", "")
m2 = r2.json().get("message", "")
results["F02_enum"] = {
    "notexist": r1.status_code,
    "admin_wrong": r2.status_code,
    "notexist_msg": m1,
    "admin_wrong_msg": m2,
    "PASS" if r1.status_code == r2.status_code == 401 and m1 == m2 else "FAIL": "都应401且消息一致",
}

print(json.dumps(results, indent=2, ensure_ascii=False))
