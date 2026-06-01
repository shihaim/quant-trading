from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.auth.credentials import CredentialRotationError, CredentialValidationError, UserCredentialService
from trader.auth.service import AuthService
from trader.data.db import Base
from trader.data.models import UserExchangeCredential

VALID_ACCESS_KEY = "A" * 40
VALID_SECRET_KEY = "S" * 40
NEXT_ACCESS_KEY = "B" * 40
NEXT_SECRET_KEY = "T" * 40


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_set_exchange_credentials_encrypts_at_rest_and_returns_status():
    session = _session()
    user = AuthService(session).signup(email="cred@example.com", password="strong-pass-123")
    service = UserCredentialService(session, encryption_key="cred-unit-test-key")

    status = service.set_exchange_credentials(
        user=user,
        exchange="UPBIT",
        access_key=VALID_ACCESS_KEY,
        secret_key=VALID_SECRET_KEY,
    )

    assert status["has_credentials"] is True
    assert status["is_valid"] is True
    assert status["status_level"] == "connected"
    assert status["next_action"] is None
    assert status["exchange"] == "UPBIT"
    assert status["access_key_masked"] == "AAAA...AAAA"
    assert status["access_key_fingerprint_prefix"] is not None

    row = session.execute(select(UserExchangeCredential).where(UserExchangeCredential.user_id == user.id)).scalar_one()
    assert row.access_key_encrypted != VALID_ACCESS_KEY
    assert row.secret_key_encrypted != VALID_SECRET_KEY
    assert row.access_key_encrypted.startswith("v2.")
    assert row.secret_key_encrypted.startswith("v2.")
    assert row.key_version == "v1"
    assert VALID_ACCESS_KEY not in row.access_key_encrypted
    assert VALID_SECRET_KEY not in row.secret_key_encrypted


def test_get_exchange_credential_status_returns_empty_without_credentials():
    session = _session()
    user = AuthService(session).signup(email="nocred@example.com", password="strong-pass-123")
    service = UserCredentialService(session, encryption_key="cred-unit-test-key")

    status = service.get_exchange_credential_status(user=user, exchange="UPBIT")

    assert status["has_credentials"] is False
    assert status["is_valid"] is False
    assert status["status_level"] == "missing"
    assert status["next_action"] == "register_credentials"
    assert status["access_key_masked"] is None


def test_get_exchange_credential_status_marks_unreadable_secret_needs_attention():
    session = _session()
    user = AuthService(session).signup(email="brokencred@example.com", password="strong-pass-123")
    UserCredentialService(session, encryption_key="original-key").set_exchange_credentials(
        user=user,
        exchange="UPBIT",
        access_key=VALID_ACCESS_KEY,
        secret_key=VALID_SECRET_KEY,
    )
    service = UserCredentialService(session, encryption_key="different-key", keyring={"v1": "different-key"})

    status = service.get_exchange_credential_status(user=user, exchange="UPBIT")

    assert status["has_credentials"] is True
    assert status["is_valid"] is False
    assert status["status_level"] == "needs_attention"
    assert status["next_action"] == "update_credentials"


def test_set_exchange_credentials_validates_input():
    session = _session()
    user = AuthService(session).signup(email="badcred@example.com", password="strong-pass-123")
    service = UserCredentialService(session, encryption_key="cred-unit-test-key")

    with pytest.raises(CredentialValidationError, match="access_key is required"):
        service.set_exchange_credentials(
            user=user,
            exchange="UPBIT",
            access_key="",
            secret_key=VALID_SECRET_KEY,
        )

    with pytest.raises(CredentialValidationError, match="access_key must be 40 characters"):
        service.set_exchange_credentials(
            user=user,
            exchange="UPBIT",
            access_key="too-short",
            secret_key=VALID_SECRET_KEY,
        )

    with pytest.raises(CredentialValidationError, match="secret_key must be 40 characters"):
        service.set_exchange_credentials(
            user=user,
            exchange="UPBIT",
            access_key=VALID_ACCESS_KEY,
            secret_key="too-short",
        )

    with pytest.raises(CredentialValidationError, match="only UPBIT is supported"):
        service.set_exchange_credentials(
            user=user,
            exchange="BINANCE",
            access_key=VALID_ACCESS_KEY,
            secret_key=VALID_SECRET_KEY,
        )


def test_key_rotation_reencrypts_rows_and_preserves_plaintext():
    session = _session()
    user = AuthService(session).signup(email="rotate@example.com", password="strong-pass-123")
    base_service = UserCredentialService(
        session,
        encryption_key="cred-unit-test-key-v1",
        active_key_version="v1",
    )
    base_service.set_exchange_credentials(
        user=user,
        exchange="UPBIT",
        access_key=VALID_ACCESS_KEY,
        secret_key=VALID_SECRET_KEY,
    )

    rotating_service = UserCredentialService(
        session,
        encryption_key="cred-unit-test-key-v1",
        active_key_version="v2",
        keyring={"v1": "cred-unit-test-key-v1", "v2": "cred-unit-test-key-v2"},
    )
    result = rotating_service.rotate_exchange_credentials(exchange="UPBIT", target_key_version="v2", dry_run=False)

    assert result["rotated"] == 1
    assert result["failed"] == 0
    row = session.execute(select(UserExchangeCredential).where(UserExchangeCredential.user_id == user.id)).scalar_one()
    assert row.key_version == "v2"

    status = rotating_service.get_exchange_credential_status(user=user, exchange="UPBIT")
    assert status["is_valid"] is True
    assert status["key_version"] == "v2"
    access, secret = rotating_service.get_exchange_credentials_by_user_id(user_id=user.id, exchange="UPBIT")
    assert access == VALID_ACCESS_KEY
    assert secret == VALID_SECRET_KEY


def test_key_rotation_requires_target_key_configuration():
    session = _session()
    user = AuthService(session).signup(email="rotate-missing-key@example.com", password="strong-pass-123")
    UserCredentialService(session, encryption_key="cred-unit-test-key").set_exchange_credentials(
        user=user,
        exchange="UPBIT",
        access_key=VALID_ACCESS_KEY,
        secret_key=VALID_SECRET_KEY,
    )
    service = UserCredentialService(
        session,
        encryption_key="cred-unit-test-key",
        active_key_version="v1",
        keyring={"v1": "cred-unit-test-key"},
    )
    with pytest.raises(CredentialRotationError, match="not configured"):
        service.rotate_exchange_credentials(exchange="UPBIT", target_key_version="v2", dry_run=False)

