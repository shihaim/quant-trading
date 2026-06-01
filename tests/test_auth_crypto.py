from __future__ import annotations

import pytest

from trader.auth.crypto import SecretCryptoError, decrypt_secret, encrypt_secret


def test_encrypt_and_decrypt_secret_roundtrip():
    token = encrypt_secret("upbit-secret-value", encryption_key="unit-test-encryption-key")
    restored = decrypt_secret(token, encryption_key="unit-test-encryption-key")

    assert restored == "upbit-secret-value"
    assert token != "upbit-secret-value"
    assert token.startswith("v2.")


def test_decrypt_secret_rejects_tampered_ciphertext():
    token = encrypt_secret("upbit-secret-value", encryption_key="unit-test-encryption-key")
    version, nonce_b64, cipher_b64 = token.split(".", 2)
    tampered_cipher_b64 = ("A" if cipher_b64[0] != "A" else "B") + cipher_b64[1:]
    tampered = f"{version}.{nonce_b64}.{tampered_cipher_b64}"

    with pytest.raises(SecretCryptoError, match="ciphertext_auth_failed"):
        decrypt_secret(tampered, encryption_key="unit-test-encryption-key")


def test_decrypt_secret_rejects_wrong_key():
    token = encrypt_secret("upbit-secret-value", encryption_key="unit-test-encryption-key")

    with pytest.raises(SecretCryptoError, match="ciphertext_auth_failed"):
        decrypt_secret(token, encryption_key="different-key")


def test_decrypt_secret_supports_legacy_v1_ciphertext():
    legacy_token = "v1.pNRyndGZgtaXSBbhvGeHRg.Q8C2IPNKmwl9uj6RDtMj7V47Tw.Bgk0rL6ThC0-UeEMVk9j3ZQYx6amr6cw5H400j99qEI"

    restored = decrypt_secret(legacy_token, encryption_key="legacy-unit-test-key")

    assert restored == "legacy-secret-value"

