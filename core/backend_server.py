"""真实后端被测系统启停器：用子进程起 uvicorn，测完优雅关闭。

与 core/mock_server.py 的关系：
- mock_server 用同进程内 Flask 起一个假服务（dev 环境）
- backend_server 用独立子进程起真实 FastAPI 后端（real 环境）

设计要点（学习重点）：
1. 端口探测就绪：子进程刚起时还接不了请求，轮询 /health 直到 200 再返回给 fixture，避免测试抢跑。
2. 测试完优雅终止：先 SIGTERM，超时再 kill，避免残留进程占用端口。
3. 隔离：每次启动都会让后端 lifespan 清空 DB + 重建表（见 apps/backend/seed.py），保证测试干净。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

from utils.logger import get_logger
from utils.paths import PROJECT_ROOT

logger = get_logger("backend")

# 后端默认监听端口（与 apps/backend/main.py 的 BACKEND_PORT 对齐）
DEFAULT_PORT = 8000


def _pick_free_port(host: str = "127.0.0.1") -> int:
    """让系统分配一个空闲端口，避免多实例抢端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        return sock.getsockname()[1]


class BackendServer:
    """子进程方式起/停 FastAPI 后端。"""

    def __init__(self, host: str = "127.0.0.1", port: int | None = None):
        self.host = host
        self.port = port if port is not None else _pick_free_port(host)
        self._proc: subprocess.Popen | None = None
        # 后端启动前清掉旧的 DB 文件，让 lifespan 重建一个干净的库
        db_path = Path(os.getenv("BACKEND_DB_PATH", PROJECT_ROOT / "apps" / "backend" / "dev.db"))
        if db_path.exists():
            try:
                db_path.unlink()
                logger.info("已清空旧 DB 文件: %s", db_path)
            except OSError:
                pass

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def auth_url(self) -> str:
        return f"{self.base_url}/api/auth/login"

    def start(self, ready_timeout: float = 15.0) -> "BackendServer":
        """启动 uvicorn 子进程并等待就绪。"""
        env = os.environ.copy()
        env["BACKEND_PORT"] = str(self.port)

        cmd = [
            sys.executable, "-m", "uvicorn",
            "apps.backend.main:app",
            "--host", self.host,
            "--port", str(self.port),
            "--log-level", "warning",
        ]
        logger.info("启动后端子进程: %s", " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._wait_ready(ready_timeout)
        logger.info("后端已就绪: %s", self.base_url)
        return self

    def _wait_ready(self, timeout: float) -> None:
        deadline = time.time() + timeout
        probe = requests.Session()
        probe.trust_env = False
        last_err = None
        while time.time() < deadline:
            # 进程提前挂了 → 直接抛
            if self._proc is not None and self._proc.poll() is not None:
                out = self._proc.stdout.read() if self._proc.stdout else ""
                raise RuntimeError(f"后端进程已退出 (code={self._proc.returncode}):\n{out[-2000:]}")
            try:
                r = probe.get(f"{self.base_url}/health", timeout=0.5)
                if r.status_code == 200:
                    return
            except requests.RequestException as e:
                last_err = e
                time.sleep(0.2)
        raise RuntimeError(f"后端在 {timeout}s 内未就绪 ({self.base_url}): {last_err}")

    def stop(self) -> None:
        if self._proc is None:
            return
        logger.info("停止后端子进程: %s", self.base_url)
        self._proc.terminate()
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("后端进程未在 10s 内退出，强制 kill")
            self._proc.kill()
            self._proc.wait(timeout=5)
        finally:
            self._proc = None


def start_backend_server(host: str = "127.0.0.1", port: int | None = None) -> BackendServer:
    """便捷构造 + 启动。"""
    return BackendServer(host=host, port=port).start()
