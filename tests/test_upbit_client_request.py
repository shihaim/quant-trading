from __future__ import annotations

import httpx
import pytest

import trader.exchange.upbit_client as upbit_client_module
from trader.exchange.upbit_client import UpbitClient


def _build_client(retry_max: int = 3) -> UpbitClient:
    client = UpbitClient(
        base_url="https://api.upbit.com",
        access_key="access",
        secret_key="secret",
        retry_max=retry_max,
        retry_backoff_seconds=0.0,
    )
    client.rate_limiter.wait = lambda: None
    return client


def test_request_unauthorized_does_not_retry(monkeypatch: pytest.MonkeyPatch):
    client = _build_client(retry_max=3)
    calls = {"count": 0}

    def fake_request(method, url, params=None, headers=None):
        calls["count"] += 1
        req = httpx.Request(method, url, params=params, headers=headers)
        return httpx.Response(401, request=req, json={"error": "unauthorized"})

    monkeypatch.setattr(client.client, "request", fake_request)

    with pytest.raises(httpx.HTTPStatusError):
        client._request("GET", "/v1/orders/open", params={"market": "KRW-BTC"}, auth=True)

    assert calls["count"] == 1
    client.close()


def test_request_retryable_status_retries_with_fresh_auth_header(monkeypatch: pytest.MonkeyPatch):
    client = _build_client(retry_max=3)
    auth_headers: list[str] = []
    requests_seen = {"count": 0}

    def fake_build_auth_header(access_key: str, secret_key: str, params=None):
        token = f"Bearer token-{len(auth_headers) + 1}"
        auth_headers.append(token)
        return {"Authorization": token}

    def fake_request(method, url, params=None, headers=None):
        requests_seen["count"] += 1
        req = httpx.Request(method, url, params=params, headers=headers)
        if requests_seen["count"] == 1:
            return httpx.Response(500, request=req, json={"error": "server"})
        return httpx.Response(200, request=req, json={"ok": True})

    monkeypatch.setattr(upbit_client_module, "build_auth_header", fake_build_auth_header)
    monkeypatch.setattr(client.client, "request", fake_request)

    payload = client._request("GET", "/v1/orders/open", params={"market": "KRW-BTC"}, auth=True)

    assert payload == {"ok": True}
    assert requests_seen["count"] == 2
    assert auth_headers == ["Bearer token-1", "Bearer token-2"]
    client.close()
