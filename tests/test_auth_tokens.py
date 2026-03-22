from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from trader.auth.tokens import TokenError, decode_access_token, issue_access_token


def test_issue_and_decode_access_token_roundtrip():
    token = issue_access_token(user_id=7, secret="unit-test-secret", ttl_seconds=120, now_ts=1_000)
    claims = decode_access_token(token, secret="unit-test-secret", now_ts=1_010)

    assert claims.user_id == 7
    assert claims.token_version == 1
    assert claims.issued_at == 1_000
    assert claims.expires_at == 1_120


def test_decode_access_token_rejects_tampered_signature():
    token = issue_access_token(user_id=7, secret="unit-test-secret", ttl_seconds=120, now_ts=1_000)
    payload, signature = token.split(".", 1)
    tampered = f"{payload}.{signature[:-1]}A"

    with pytest.raises(TokenError, match="invalid_signature"):
        decode_access_token(tampered, secret="unit-test-secret", now_ts=1_010)


def test_decode_access_token_rejects_expired_token():
    token = issue_access_token(user_id=7, secret="unit-test-secret", ttl_seconds=5, now_ts=1_000)

    with pytest.raises(TokenError, match="expired"):
        decode_access_token(token, secret="unit-test-secret", now_ts=1_006)


def test_decode_access_token_defaults_token_version_for_legacy_payload():
    token = issue_access_token(user_id=7, token_version=3, secret="unit-test-secret", ttl_seconds=120, now_ts=1_000)
    payload_part, _ = token.split(".", 1)
    padding = "=" * (-len(payload_part) % 4)
    payload = json.loads(base64.urlsafe_b64decode((payload_part + padding).encode("ascii")).decode("utf-8"))
    payload.pop("tv", None)
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    legacy_payload_part = base64.urlsafe_b64encode(payload_raw).decode("ascii").rstrip("=")
    signature = hmac.new(b"unit-test-secret", legacy_payload_part.encode("ascii"), hashlib.sha256).digest()
    legacy_signature_part = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    legacy_token = f"{legacy_payload_part}.{legacy_signature_part}"

    claims = decode_access_token(legacy_token, secret="unit-test-secret", now_ts=1_010)

    assert claims.user_id == 7
    assert claims.token_version == 1
