import json

import httpx
import pytest

from veqen import Veqen, VeqenError


def make(handler, **kwargs):
    return Veqen("vq_live_test", base_url="https://api.test", transport=httpx.MockTransport(handler), **kwargs)


def test_signup_sends_auth_and_drops_empty_fields():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"risk": {"verdict": "refuse"}})

    result = make(handler).signup(email="a@b.com", ip="1.2.3.4")
    assert result["risk"]["verdict"] == "refuse"
    assert seen == {"auth": "Bearer vq_live_test", "path": "/v1/signup/check", "body": {"email": "a@b.com", "ip": "1.2.3.4", "verify_mailbox": False}}


def test_errors_raise_with_type():
    def handler(request):
        return httpx.Response(402, json={"error": {"type": "insufficient_credits", "message": "Buy credits"}}, headers={"X-Request-Id": "r1"})

    with pytest.raises(VeqenError) as info:
        make(handler).email("a@b.com")
    assert info.value.status == 402 and info.value.type == "insufficient_credits" and info.value.request_id == "r1"


def test_retries_on_429(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 2:
            return httpx.Response(429, json={"error": {"type": "rate_limited", "message": "slow"}}, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"ok": True})

    assert make(handler).ip("1.2.3.4") == {"ok": True}
    assert len(calls) == 2


def test_batch_chunks_by_100():
    sizes = []

    def handler(request):
        emails = json.loads(request.content)["emails"]
        sizes.append(len(emails))
        return httpx.Response(200, json={"results": [{"email": e} for e in emails], "count": len(emails)})

    results = make(handler).emails([f"u{i}@a.com" for i in range(250)])
    assert sizes == [100, 100, 50] and len(results) == 250


def test_idempotency_header():
    def handler(request):
        assert request.headers["Idempotency-Key"] == "k1"
        return httpx.Response(200, json={})

    make(handler).phone("+447400123456", idempotency_key="k1")


def test_requires_key(monkeypatch):
    monkeypatch.delenv("VEQEN_API_KEY", raising=False)
    with pytest.raises(ValueError):
        Veqen()


def test_retry_preserves_automatic_idempotency_key(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    keys = []

    def handler(request):
        keys.append(request.headers["Idempotency-Key"])
        if len(keys) == 1:
            raise httpx.ReadTimeout("Response lost after server charged", request=request)
        return httpx.Response(200, json={})

    client = make(handler)
    client.ip("1.2.3.4")
    client.ip("1.2.3.4")
    assert keys[0] == keys[1]
    assert keys[1] != keys[2]
