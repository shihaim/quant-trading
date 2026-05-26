from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.auth.crypto import SecretCryptoError, decrypt_secret, encrypt_secret
from trader.data.models import User, UserExchangeCredential

EXCHANGE_UPBIT = "UPBIT"
UPBIT_API_KEY_LENGTH = 40


class CredentialValidationError(ValueError):
    """Invalid credential input."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CredentialRotationError(ValueError):
    """Credential key rotation failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _iso_utc(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    normalized = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _mask_access_key(access_key: str) -> str:
    if len(access_key) <= 8:
        visible = access_key[-2:] if len(access_key) >= 2 else access_key
        return f"{'*' * max(0, len(access_key) - len(visible))}{visible}"
    return f"{access_key[:4]}...{access_key[-4:]}"


def _normalize_exchange(exchange: str | None) -> str:
    raw = (exchange or EXCHANGE_UPBIT).strip().upper()
    return raw or EXCHANGE_UPBIT


def _validate_exchange(exchange: str) -> None:
    if exchange != EXCHANGE_UPBIT:
        raise CredentialValidationError("unsupported_exchange", "only UPBIT is supported")


def _validate_access_key(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise CredentialValidationError("access_key_required", "access_key is required")
    if len(normalized) != UPBIT_API_KEY_LENGTH:
        raise CredentialValidationError("invalid_access_key", "access_key must be 40 characters")
    return normalized


def _validate_secret_key(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise CredentialValidationError("secret_key_required", "secret_key is required")
    if len(normalized) != UPBIT_API_KEY_LENGTH:
        raise CredentialValidationError("invalid_secret_key", "secret_key must be 40 characters")
    return normalized


def _fingerprint_access_key(access_key: str) -> str:
    return hashlib.sha256(access_key.encode("utf-8")).hexdigest()


def _normalize_key_version(raw: str | None, fallback: str = "v1") -> str:
    normalized = str(raw or "").strip().lower()
    if not normalized:
        return fallback
    return normalized[:32]


def _parse_keyring_json(raw: str | None) -> dict[str, str]:
    if not str(raw or "").strip():
        return {}
    try:
        payload = json.loads(str(raw))
    except Exception as exc:
        raise CredentialValidationError("invalid_keyring", "keyring must be valid JSON object") from exc
    if not isinstance(payload, dict):
        raise CredentialValidationError("invalid_keyring", "keyring must be valid JSON object")
    out: dict[str, str] = {}
    for key_version, key_value in payload.items():
        normalized_version = _normalize_key_version(str(key_version or ""))
        if not normalized_version:
            continue
        secret = str(key_value or "").strip()
        if secret:
            out[normalized_version] = secret
    return out


def _status_payload(row: UserExchangeCredential | None, *, is_valid: bool) -> dict:
    if row is None:
        return {
            "exchange": EXCHANGE_UPBIT,
            "has_credentials": False,
            "is_valid": False,
            "status_level": "missing",
            "next_action": "register_credentials",
            "key_version": None,
            "access_key_masked": None,
            "access_key_fingerprint_prefix": None,
            "updated_at_utc": None,
        }

    status_level = "connected" if is_valid else "needs_attention"
    return {
        "exchange": row.exchange,
        "has_credentials": True,
        "is_valid": is_valid,
        "status_level": status_level,
        "next_action": None if is_valid else "update_credentials",
        "key_version": getattr(row, "key_version", "v1"),
        "access_key_masked": row.access_key_masked,
        "access_key_fingerprint_prefix": row.access_key_fingerprint[:12],
        "updated_at_utc": _iso_utc(row.updated_at),
    }


class UserCredentialService:
    """Per-user encrypted exchange credential management."""

    def __init__(
        self,
        session: Session,
        *,
        encryption_key: str,
        active_key_version: str = "v1",
        keyring_json: str | None = None,
        keyring: dict[str, str] | None = None,
    ):
        self.session = session
        self.encryption_key = encryption_key
        self.active_key_version = _normalize_key_version(active_key_version)
        resolved: dict[str, str] = {}
        if keyring:
            for key_version, key_value in keyring.items():
                normalized = _normalize_key_version(key_version)
                if normalized and str(key_value or "").strip():
                    resolved[normalized] = str(key_value)
        resolved.update(_parse_keyring_json(keyring_json))
        if self.active_key_version not in resolved:
            resolved[self.active_key_version] = encryption_key
        if "v1" not in resolved and encryption_key:
            resolved["v1"] = encryption_key
        self.keyring = resolved

    def _encrypt_key(self) -> str:
        key = str(self.keyring.get(self.active_key_version, "")).strip()
        if not key:
            raise CredentialValidationError("encryption_key_required", "active credential key is required")
        return key

    def _decrypt_key_for_row(self, row: UserExchangeCredential) -> str:
        key_version = _normalize_key_version(getattr(row, "key_version", None), fallback="v1")
        key = str(self.keyring.get(key_version, "")).strip()
        if key:
            return key
        fallback = str(self.encryption_key or "").strip()
        if fallback:
            return fallback
        raise CredentialValidationError("encryption_key_required", "credential decryption key is required")

    def _decrypt_row(self, row: UserExchangeCredential) -> tuple[str, str]:
        key = self._decrypt_key_for_row(row)
        access = decrypt_secret(row.access_key_encrypted, encryption_key=key)
        secret = decrypt_secret(row.secret_key_encrypted, encryption_key=key)
        return access, secret

    def set_exchange_credentials(
        self,
        *,
        user: User,
        exchange: str = EXCHANGE_UPBIT,
        access_key: str,
        secret_key: str,
    ) -> dict:
        normalized_exchange = _normalize_exchange(exchange)
        _validate_exchange(normalized_exchange)
        normalized_access_key = _validate_access_key(access_key)
        normalized_secret_key = _validate_secret_key(secret_key)

        row = self.session.execute(
            select(UserExchangeCredential).where(
                UserExchangeCredential.user_id == user.id,
                UserExchangeCredential.exchange == normalized_exchange,
            )
        ).scalar_one_or_none()
        if row is None:
            row = UserExchangeCredential(
                user_id=user.id,
                exchange=normalized_exchange,
                access_key_encrypted="",
                secret_key_encrypted="",
                access_key_masked="",
                access_key_fingerprint="",
            )
            self.session.add(row)
            self.session.flush()

        row.access_key_encrypted = encrypt_secret(
            normalized_access_key,
            encryption_key=self._encrypt_key(),
        )
        row.secret_key_encrypted = encrypt_secret(
            normalized_secret_key,
            encryption_key=self._encrypt_key(),
        )
        row.key_version = self.active_key_version
        row.access_key_masked = _mask_access_key(normalized_access_key)
        row.access_key_fingerprint = _fingerprint_access_key(normalized_access_key)
        self.session.commit()
        self.session.refresh(row)
        return _status_payload(row, is_valid=True)

    def get_exchange_credential_status(self, *, user: User, exchange: str = EXCHANGE_UPBIT) -> dict:
        normalized_exchange = _normalize_exchange(exchange)
        _validate_exchange(normalized_exchange)
        row = self.session.execute(
            select(UserExchangeCredential).where(
                UserExchangeCredential.user_id == user.id,
                UserExchangeCredential.exchange == normalized_exchange,
            )
        ).scalar_one_or_none()
        if row is None:
            return _status_payload(None, is_valid=False)

        is_valid = True
        try:
            self._decrypt_row(row)
        except SecretCryptoError:
            is_valid = False

        return _status_payload(row, is_valid=is_valid)

    def get_exchange_credentials_by_user_id(self, *, user_id: int, exchange: str = EXCHANGE_UPBIT) -> tuple[str, str]:
        normalized_exchange = _normalize_exchange(exchange)
        _validate_exchange(normalized_exchange)
        row = self.session.execute(
            select(UserExchangeCredential).where(
                UserExchangeCredential.user_id == max(1, int(user_id)),
                UserExchangeCredential.exchange == normalized_exchange,
            )
        ).scalar_one_or_none()
        if row is None:
            raise CredentialValidationError("credentials_required", "upbit credentials are required")
        try:
            return self._decrypt_row(row)
        except SecretCryptoError as exc:
            raise CredentialValidationError("credentials_invalid", "stored credentials are invalid") from exc

    def rotate_exchange_credentials(
        self,
        *,
        exchange: str = EXCHANGE_UPBIT,
        target_key_version: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        normalized_exchange = _normalize_exchange(exchange)
        _validate_exchange(normalized_exchange)
        target_version = _normalize_key_version(target_key_version, fallback=self.active_key_version)
        target_key = str(self.keyring.get(target_version, "")).strip()
        if not target_key:
            raise CredentialRotationError("target_key_missing", f"key version '{target_version}' is not configured")

        rows = self.session.execute(
            select(UserExchangeCredential).where(UserExchangeCredential.exchange == normalized_exchange)
        ).scalars().all()
        scanned = len(rows)
        rotated = 0
        skipped = 0
        failed = 0
        failed_user_ids: list[int] = []

        for row in rows:
            current_version = _normalize_key_version(getattr(row, "key_version", None), fallback="v1")
            if current_version == target_version:
                skipped += 1
                continue
            try:
                access, secret = self._decrypt_row(row)
            except Exception:
                failed += 1
                failed_user_ids.append(int(row.user_id))
                continue
            if dry_run:
                rotated += 1
                continue
            row.access_key_encrypted = encrypt_secret(access, encryption_key=target_key)
            row.secret_key_encrypted = encrypt_secret(secret, encryption_key=target_key)
            row.key_version = target_version
            rotated += 1

        if not dry_run:
            self.session.commit()

        return {
            "exchange": normalized_exchange,
            "target_key_version": target_version,
            "dry_run": bool(dry_run),
            "scanned": scanned,
            "rotated": rotated,
            "skipped": skipped,
            "failed": failed,
            "failed_user_ids": failed_user_ids[:50],
        }

