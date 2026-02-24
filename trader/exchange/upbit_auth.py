from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from base64 import urlsafe_b64encode
from typing import Any
from urllib.parse import unquote, urlencode


def _b64url(data: bytes) -> str:
    """JWT 인코딩에 맞는 base64url 문자열로 변환한다."""
    return urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _jwt_hs512(payload: dict[str, Any], secret: str) -> str:
    """HS512 방식으로 JWT 토큰을 생성한다."""
    header = {"alg": "HS512", "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha512).digest()
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"


def build_auth_header(access_key: str, secret_key: str, params: dict[str, Any] | None = None) -> dict[str, str]:
    """업비트 인증용 Authorization 헤더를 생성한다."""
    payload: dict[str, Any] = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
    }
    if params:
        # Upbit expects query_hash from a non-percent-encoded query string.
        query_string = unquote(urlencode(params, doseq=True))
        payload["query_hash"] = hashlib.sha512(query_string.encode("utf-8")).hexdigest()
        payload["query_hash_alg"] = "SHA512"
    token = _jwt_hs512(payload, secret_key)
    return {"Authorization": f"Bearer {token}"}
