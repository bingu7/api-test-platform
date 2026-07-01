import time
import requests


class TokenManager:
    def __init__(self, auth_url: str, credentials: dict):
        self.auth_url = auth_url
        self.credentials = credentials
        self._token = None
        self._expires_at = 0

    def _fetch_token(self) -> dict:
        response = requests.post(self.auth_url, json=self.credentials, timeout=10)
        data = response.json()
        return {
            "token": data["access_token"],
            "expires_at": time.time() + data.get("expires_in", 3600) - 60,
        }

    def get_token(self) -> str:
        if not self._token or time.time() >= self._expires_at:
            result = self._fetch_token()
            self._token = result["token"]
            self._expires_at = result["expires_at"]
            print(f"[Token] 已刷新，有效期至 {time.ctime(self._expires_at)}")
        return self._token