"""接口压测脚本（标准库 concurrent.futures，不依赖 locust）。

用法（先起后端）:
    python -m scripts.perf_test --base-url http://127.0.0.1:8000 --n 200 --c 20

输出：成功率、平均/最大/P95 延迟、QPS。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time

import requests


def benchmark(base_url: str, path: str, n: int, concurrency: int) -> dict:
    """对 GET base_url+path 打点 n 次，concurrency 并发。"""
    session = requests.Session()
    session.trust_env = False
    url = base_url.rstrip("/") + path

    def one(_):
        t = time.perf_counter()
        try:
            r = session.get(url, timeout=10)
            ok = r.status_code == 200
        except requests.RequestException:
            ok = False
        return time.perf_counter() - t, ok

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(one, range(n)))
    total = time.perf_counter() - start

    latencies = [x for x, _ in results]
    ok_count = sum(1 for _, ok in results if ok)
    sorted_l = sorted(latencies)
    p95 = sorted_l[int(len(sorted_l) * 0.95)] if len(sorted_l) >= 20 else max(sorted_l)
    return {
        "n": n, "concurrency": concurrency,
        "ok": ok_count, "fail": n - ok_count,
        "avg_ms": statistics.mean(latencies) * 1000,
        "max_ms": max(latencies) * 1000,
        "p95_ms": p95 * 1000,
        "qps": n / total if total > 0 else 0,
        "total_s": total,
    }


def main():
    p = argparse.ArgumentParser(description="轻量接口压测")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--path", default="/api/products")
    p.add_argument("-n", type=int, default=100, help="总请求数")
    p.add_argument("-c", type=int, default=10, help="并发数")
    args = p.parse_args()

    print(f"压测 {args.base_url}{args.path}  n={args.n} c={args.c}")
    r = benchmark(args.base_url, args.path, args.n, args.c)
    print(f"成功: {r['ok']}/{r['n']}  失败: {r['fail']}")
    print(f"平均: {r['avg_ms']:.1f}ms  最大: {r['max_ms']:.1f}ms  P95: {r['p95_ms']:.1f}ms")
    print(f"QPS: {r['qps']:.1f}  总时长: {r['total_s']:.2f}s")


if __name__ == "__main__":
    main()
