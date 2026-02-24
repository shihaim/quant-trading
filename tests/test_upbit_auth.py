from __future__ import annotations

import base64
import hashlib
import json
import uuid

from trader.exchange.upbit_auth import build_auth_header


def _decode_payload(authorization_header: str) -> dict:
    token = authorization_header.split(" ", 1)[1]
    payload_b64 = token.split(".")[1]
    padding = "=" * (-len(payload_b64) % 4)
    raw = base64.urlsafe_b64decode((payload_b64 + padding).encode("utf-8"))
    return json.loads(raw.decode("utf-8"))


def test_build_auth_header_hashes_unquoted_query(monkeypatch):
    monkeypatch.setattr(uuid, "uuid4", lambda: "fixed-nonce")
    header = build_auth_header(
        "access-key",
        "secret-key",
        params={"states[]": ["wait", "watch"], "market": "KRW-BTC"},
    )
    payload = _decode_payload(header["Authorization"])
    expected_query = "states[]=wait&states[]=watch&market=KRW-BTC"
    expected_hash = hashlib.sha512(expected_query.encode("utf-8")).hexdigest()
    assert payload["nonce"] == "fixed-nonce"
    assert payload["query_hash"] == expected_hash
    assert payload["query_hash_alg"] == "SHA512"


def test_build_auth_header_without_params_has_no_query_hash(monkeypatch):
    monkeypatch.setattr(uuid, "uuid4", lambda: "fixed-nonce")
    header = build_auth_header("access-key", "secret-key", params=None)
    payload = _decode_payload(header["Authorization"])
    assert payload["nonce"] == "fixed-nonce"
    assert "query_hash" not in payload
    assert "query_hash_alg" not in payload
