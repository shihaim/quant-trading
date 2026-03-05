from __future__ import annotations

import pytest

from trader.auth.tokens import TokenError, decode_access_token, issue_access_token


def test_issue_and_decode_access_token_roundtrip():
    token = issue_access_token(user_id=7, secret="unit-test-secret", ttl_seconds=120, now_ts=1_000)
    claims = decode_access_token(token, secret="unit-test-secret", now_ts=1_010)

    assert claims.user_id == 7
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

