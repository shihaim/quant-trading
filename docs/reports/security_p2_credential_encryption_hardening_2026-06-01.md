# Security P2 Credential Encryption Hardening

Date: 2026-06-01

## Scope

P2 replaces the local custom credential encryption primitive with standard AEAD encryption for newly written Upbit credentials.

## Behavior

- New credential writes use AES-GCM ciphertext tokens with a `v2` prefix.
- Existing `v1` ciphertext remains decryptable for backward compatibility.
- Existing keyring and `key_version` rotation behavior is preserved.
- Rotation through `POST /api/admin/credentials/rotate` can re-encrypt old rows into the active key version and current `v2` token format.

## Operator Notes

- Keep old keys in `OPS_API_CREDENTIALS_KEYRING_JSON` until `dry_run=true` rotation reports `failed=0`.
- Do not remove prior keys before validating `/api/me/credentials/upbit` and scheduler credential loading.
- Runtime secrets stay in deployment environment configuration, not source code or container images.

## Verification

- `uv run pytest tests/test_auth_crypto.py tests/test_user_credentials_service.py`
