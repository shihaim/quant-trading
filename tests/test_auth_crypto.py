from __future__ import annotations

import pytest

from trader.auth.crypto import SecretCryptoError, decrypt_secret, encrypt_secret


def test_encrypt_and_decrypt_secret_roundtrip():
    token = encrypt_secret("upbit-secret-value", encryption_key="unit-test-encryption-key")
    restored = decrypt_secret(token, encryption_key="unit-test-encryption-key")

    assert restored == "upbit-secret-value"
    assert token != "upbit-secret-value"


def test_decrypt_secret_rejects_tampered_ciphertext():
    token = encrypt_secret("upbit-secret-value", encryption_key="unit-test-encryption-key")
    version, nonce_b64, cipher_b64, tag_b64 = token.split(".", 3)
    tampered_tag_b64 = ("A" if tag_b64[0] != "A" else "B") + tag_b64[1:]
    tampered = f"{version}.{nonce_b64}.{cipher_b64}.{tampered_tag_b64}"

    with pytest.raises(SecretCryptoError, match="ciphertext_auth_failed"):
        decrypt_secret(tampered, encryption_key="unit-test-encryption-key")


def test_decrypt_secret_rejects_wrong_key():
    token = encrypt_secret("upbit-secret-value", encryption_key="unit-test-encryption-key")

    with pytest.raises(SecretCryptoError, match="ciphertext_auth_failed"):
        decrypt_secret(token, encryption_key="different-key")

