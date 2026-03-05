from __future__ import annotations

import base64
import hashlib
import hmac
import os


class SecretCryptoError(ValueError):
    """Credential encryption/decryption error."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def _derive_key(secret: str) -> bytes:
    if not secret:
        raise SecretCryptoError("encryption_key_required")
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _keystream(*, key: bytes, nonce: bytes, length: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    produced = 0
    while produced < length:
        counter_bytes = counter.to_bytes(4, "big", signed=False)
        block = hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest()
        blocks.append(block)
        produced += len(block)
        counter += 1
    return b"".join(blocks)[:length]


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def encrypt_secret(plaintext: str, *, encryption_key: str) -> str:
    if plaintext is None:
        raise SecretCryptoError("plaintext_required")
    raw = str(plaintext).encode("utf-8")
    key = _derive_key(encryption_key)
    nonce = os.urandom(16)
    cipher = _xor_bytes(raw, _keystream(key=key, nonce=nonce, length=len(raw)))
    tag = hmac.new(key, b"v1" + nonce + cipher, hashlib.sha256).digest()
    return f"v1.{_b64encode(nonce)}.{_b64encode(cipher)}.{_b64encode(tag)}"


def decrypt_secret(token: str, *, encryption_key: str) -> str:
    key = _derive_key(encryption_key)
    if not token:
        raise SecretCryptoError("ciphertext_required")

    try:
        version, nonce_b64, cipher_b64, tag_b64 = token.split(".", 3)
    except ValueError as exc:
        raise SecretCryptoError("invalid_ciphertext_format") from exc
    if version != "v1":
        raise SecretCryptoError("unsupported_ciphertext_version")

    try:
        nonce = _b64decode(nonce_b64)
        cipher = _b64decode(cipher_b64)
        provided_tag = _b64decode(tag_b64)
    except Exception as exc:
        raise SecretCryptoError("invalid_ciphertext_encoding") from exc

    expected_tag = hmac.new(key, b"v1" + nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_tag, provided_tag):
        raise SecretCryptoError("ciphertext_auth_failed")

    raw = _xor_bytes(cipher, _keystream(key=key, nonce=nonce, length=len(cipher)))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SecretCryptoError("invalid_plaintext_encoding") from exc
