from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.auth.crypto import SecretCryptoError, decrypt_secret, encrypt_secret
from trader.data.models import User, UserExchangeCredential

EXCHANGE_UPBIT = "UPBIT"


class CredentialValidationError(ValueError):
    """Invalid credential input."""

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
    if len(normalized) < 8:
        raise CredentialValidationError("invalid_access_key", "access_key is too short")
    return normalized


def _validate_secret_key(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise CredentialValidationError("secret_key_required", "secret_key is required")
    if len(normalized) < 16:
        raise CredentialValidationError("invalid_secret_key", "secret_key is too short")
    return normalized


def _fingerprint_access_key(access_key: str) -> str:
    return hashlib.sha256(access_key.encode("utf-8")).hexdigest()


def _status_payload(row: UserExchangeCredential | None, *, is_valid: bool) -> dict:
    if row is None:
        return {
            "exchange": EXCHANGE_UPBIT,
            "has_credentials": False,
            "is_valid": False,
            "access_key_masked": None,
            "access_key_fingerprint_prefix": None,
            "updated_at_utc": None,
        }

    return {
        "exchange": row.exchange,
        "has_credentials": True,
        "is_valid": is_valid,
        "access_key_masked": row.access_key_masked,
        "access_key_fingerprint_prefix": row.access_key_fingerprint[:12],
        "updated_at_utc": _iso_utc(row.updated_at),
    }


class UserCredentialService:
    """Per-user encrypted exchange credential management."""

    def __init__(self, session: Session, *, encryption_key: str):
        self.session = session
        self.encryption_key = encryption_key

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
            encryption_key=self.encryption_key,
        )
        row.secret_key_encrypted = encrypt_secret(
            normalized_secret_key,
            encryption_key=self.encryption_key,
        )
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
            decrypt_secret(row.access_key_encrypted, encryption_key=self.encryption_key)
            decrypt_secret(row.secret_key_encrypted, encryption_key=self.encryption_key)
        except SecretCryptoError:
            is_valid = False

        return _status_payload(row, is_valid=is_valid)

