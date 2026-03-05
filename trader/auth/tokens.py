from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


class TokenError(ValueError):
    """Token parsing or validation error."""


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    issued_at: int
    expires_at: int


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _sign(message: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


def issue_access_token(
    *,
    user_id: int,
    secret: str,
    ttl_seconds: int,
    now_ts: int | None = None,
) -> str:
    if not secret:
        raise TokenError("secret_required")
    if user_id <= 0:
        raise TokenError("invalid_user_id")

    issued_at = int(time.time() if now_ts is None else now_ts)
    expires_at = issued_at + max(1, int(ttl_seconds))
    payload = {
        "v": 1,
        "sub": str(user_id),
        "iat": issued_at,
        "exp": expires_at,
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64encode(payload_raw)
    signature_part = _b64encode(_sign(payload_part.encode("ascii"), secret))
    return f"{payload_part}.{signature_part}"


def decode_access_token(token: str, *, secret: str, now_ts: int | None = None) -> TokenClaims:
    if not secret:
        raise TokenError("secret_required")
    if not token:
        raise TokenError("token_required")

    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise TokenError("invalid_format") from exc

    expected_signature = _b64encode(_sign(payload_part.encode("ascii"), secret))
    if not hmac.compare_digest(expected_signature, signature_part):
        raise TokenError("invalid_signature")

    try:
        payload = json.loads(_b64decode(payload_part).decode("utf-8"))
        user_id = int(payload["sub"])
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
    except Exception as exc:
        raise TokenError("invalid_payload") from exc

    now_value = int(time.time() if now_ts is None else now_ts)
    if expires_at <= now_value:
        raise TokenError("expired")
    if issued_at <= 0 or expires_at <= issued_at:
        raise TokenError("invalid_timestamps")

    return TokenClaims(user_id=user_id, issued_at=issued_at, expires_at=expires_at)

