import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from core.token_manager import TokenManager


class BaseRequest:
    def __init__(self, base_url: str, token_manager: TokenManager):
        self.base_url = base_url.rstrip("/")
        self.token_manager = token_manager
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.timeout = (5, 15)
        return session

    def _get_headers(self) -> dict:
        token = self.token_manager.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def request(self, method: str, endpoint: str, **kwargs):
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.session.timeout
        return self.session.request(method, url, headers=headers, **kwargs)