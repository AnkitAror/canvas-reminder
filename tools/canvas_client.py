"""Minimal Canvas LMS REST client: bearer auth, Link-header pagination, retry/backoff."""
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()


class CanvasAuthError(Exception):
    """Raised when Canvas rejects the access token (401)."""


class CanvasClient:
    def __init__(self, base_url=None, token=None, timeout=30, max_retries=4):
        self.base_url = (base_url or os.environ.get("CANVAS_API_URL", "")).rstrip("/")
        token = token or os.environ.get("CANVAS_API_TOKEN", "")
        if not self.base_url or not token:
            raise RuntimeError("CANVAS_API_URL and CANVAS_API_TOKEN must be set (see .env).")
        if not self.base_url.startswith("http"):
            self.base_url = "https://" + self.base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.timeout = timeout
        self.max_retries = max_retries

    def _request(self, url, params=None):
        for attempt in range(self.max_retries + 1):
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 401:
                raise CanvasAuthError(f"Canvas rejected the token (401) for {url}")
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp
        resp.raise_for_status()
        return resp

    def get_all(self, path, params=None):
        """GET a list endpoint and follow rel="next" pagination. Returns a flat list."""
        url = path if path.startswith("http") else f"{self.base_url}/api/v1/{path.lstrip('/')}"
        params = dict(params or {})
        params.setdefault("per_page", 100)
        results = []
        while url:
            resp = self._request(url, params=params)
            data = resp.json()
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
            url = resp.links.get("next", {}).get("url")
            params = None  # next URL already carries the query string
        return results
