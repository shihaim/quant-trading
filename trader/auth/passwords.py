from __future__ import annotations

import base64
import hashlib
import hmac
import os

ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 310_000
DEFAULT_SALT_BYTES = 16
DEFAULT_KEY_BYTES = 32


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("password_required")
    salt = os.urandom(DEFAULT_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        max(1, int(iterations)),
        dklen=DEFAULT_KEY_BYTES,
    )
    return f"{ALGORITHM}${iterations}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, encoded_hash: str) -> bool:
    if not password or not encoded_hash:
        return False
    try:
        algorithm, raw_iterations, salt_b64, digest_b64 = encoded_hash.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        iterations = max(1, int(raw_iterations))
        salt = _b64decode(salt_b64)
        expected_digest = _b64decode(digest_b64)
    except Exception:
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=len(expected_digest),
    )
    return hmac.compare_digest(actual_digest, expected_digest)

