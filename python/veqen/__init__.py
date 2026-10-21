"""Official Python client for the Veqen signup-check API.

    from veqen import Veqen

    client = Veqen()  # reads VEQEN_API_KEY
    result = client.signup(email="jane@mailinator.com", ip="185.220.101.1")
    print(result["risk"]["verdict"])
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import httpx

__all__ = ["Veqen", "VeqenError"]
__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://veqen-app.com"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class VeqenError(Exception):
    """Raised for any non-2xx response. ``type`` matches the API's error.type."""

    def __init__(self, status: int, type_: str, message: str, request_id: str | None = None):
        super().__init__(f"{status} {type_}: {message}")
        self.status = status
        self.type = type_
        self.message = message
        self.request_id = request_id


class Veqen:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key or os.environ.get("VEQEN_API_KEY")
        if not key:
            raise ValueError("Pass api_key or set VEQEN_API_KEY.")
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=(base_url or os.environ.get("VEQEN_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
            headers={"Authorization": f"Bearer {key}", "User-Agent": f"veqen-python/{__version__}"},
            timeout=timeout,
            transport=transport,
        )

    # --- checks ----------------------------------------------------------------------------------

    def email(self, email: str, *, verify_mailbox: bool = False, idempotency_key: str | None = None) -> dict:
        return self._post("/v1/email/check", {"email": email, "verify_mailbox": verify_mailbox}, idempotency_key)

    def emails(self, emails: list[str], *, verify_mailbox: bool = False) -> list[dict]:
        results: list[dict] = []
        for start in range(0, len(emails), 100):
            chunk = emails[start : start + 100]
            results.extend(self._post("/v1/email/batch", {"emails": chunk, "verify_mailbox": verify_mailbox})["results"])
        return results

    def ip(self, ip: str, *, idempotency_key: str | None = None) -> dict:
        return self._post("/v1/ip/check", {"ip": ip}, idempotency_key)

    def phone(self, phone: str, country: str | None = None, *, idempotency_key: str | None = None) -> dict:
        return self._post("/v1/phone/check", {"phone": phone, "country": country}, idempotency_key)

    def domain(self, domain: str, *, idempotency_key: str | None = None) -> dict:
        return self._post("/v1/domain/check", {"domain": domain}, idempotency_key)

    def signup(
        self,
        *,
        email: str | None = None,
        ip: str | None = None,
        phone: str | None = None,
        phone_country: str | None = None,
        verify_mailbox: bool = False,
        idempotency_key: str | None = None,
    ) -> dict:
        body = {"email": email, "ip": ip, "phone": phone, "phone_country": phone_country, "verify_mailbox": verify_mailbox}
        return self._post("/v1/signup/check", {k: v for k, v in body.items() if v not in (None, "")}, idempotency_key)

    # --- account ---------------------------------------------------------------------------------

    def account(self) -> dict:
        return self._request("GET", "/v1/account")

    def usage(self, days: int = 30) -> dict:
        return self._request("GET", "/v1/usage", params={"days": days})

    # --- plumbing --------------------------------------------------------------------------------

    def _post(self, path: str, body: dict, idempotency_key: str | None = None) -> Any:
        # Reuse one key across transport/5xx retries, but generate a fresh key per logical call.
        headers = {"Idempotency-Key": idempotency_key or str(uuid.uuid4())}
        return self._request("POST", path, json=body, headers=headers)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        attempt = 0
        while True:
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.TransportError:
                if attempt >= self.max_retries:
                    raise
                attempt += 1
                time.sleep(min(2**attempt * 0.25, 4))
                continue
            if response.status_code in RETRY_STATUSES and attempt < self.max_retries:
                attempt += 1
                retry_after = response.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt * 0.25, 4))
                continue
            if response.status_code >= 400:
                try:
                    error = response.json().get("error", {})
                except ValueError:
                    error = {}
                raise VeqenError(
                    response.status_code,
                    error.get("type", "http_error"),
                    error.get("message", response.text[:200]),
                    response.headers.get("X-Request-Id"),
                )
            return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Veqen:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
