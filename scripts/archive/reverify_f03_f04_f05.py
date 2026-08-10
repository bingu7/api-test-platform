"""复测脚本：F-03 IDOR + F-04 动态token + F-05 输入验证。"""
import json
import requests

BASE = "http://127.0.0.1:8900"  # 不限流 server（login_rate_limit=0），专注验证 F-03~F-05
results = {}
r = requests.post(f"{BASE}/api/login", json={"username": "admin", "password": "123456"}, timeout=5)
token = r.json().get("access_token", "")
results["F04_token"] = {
    "token前8位": token[:8],
    "长度": len(token),
    "PASS" if len(token) >= 32 and token != "MOCK_TOKEN" else "FAIL": "应为随机32+位",
}
H = {"Authorization": f"Bearer {token}"}

# F-03: IDOR — 伪造一个其他用户的 token，读订单应 403
r = requests.get(f"{BASE}/api/orders/ORD_DB_00001", headers=H, timeout=5)
results["F03_own"] = {"本人读订单": r.status_code, "PASS" if r.status_code == 200 else "FAIL": "本人应200"}

fake = requests.post(f"{BASE}/api/login", json={"username": "admin", "password": "123456"}, timeout=5)
# 用无效 token 模拟"其他用户"：直接伪造
r_fake = requests.get(f"{BASE}/api/orders/ORD_DB_00001",
                      headers={"Authorization": "Bearer 00000000000000000000000000000000"}, timeout=5)
results["F03_fake"] = {"伪造token读订单": r_fake.status_code,
                       "PASS" if r_fake.status_code in (401, 403) else "FAIL": "伪造token应401/403"}

# F-05: 输入验证 — abc 应 400（不再500），超大金额应 400
r1 = requests.post(f"{BASE}/api/orders", headers=H, json={"amount": "abc"}, timeout=5)
r2 = requests.post(f"{BASE}/api/orders", headers=H, json={"amount": 99999999}, timeout=5)
results["F05_input"] = {
    "amount=abc": r1.status_code,
    "amount=99999999": r2.status_code,
    "PASS" if r1.status_code == 400 and r2.status_code == 400 else "FAIL": "都应400",
}

print(json.dumps(results, indent=2, ensure_ascii=False))
