from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.auth.credentials import CredentialValidationError, UserCredentialService
from trader.auth.service import AuthService
from trader.data.db import Base
from trader.data.models import UserExchangeCredential


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
        access_key="access-key-123456",
        secret_key="secret-key-1234567890",
    )

    assert status["has_credentials"] is True
    assert status["is_valid"] is True
    assert status["exchange"] == "UPBIT"
    assert status["access_key_masked"].startswith("acce...")
    assert status["access_key_fingerprint_prefix"] is not None

    row = session.execute(select(UserExchangeCredential).where(UserExchangeCredential.user_id == user.id)).scalar_one()
    assert row.access_key_encrypted != "access-key-123456"
    assert row.secret_key_encrypted != "secret-key-1234567890"
    assert "access-key-123456" not in row.access_key_encrypted
    assert "secret-key-1234567890" not in row.secret_key_encrypted


def test_get_exchange_credential_status_returns_empty_without_credentials():
    session = _session()
    user = AuthService(session).signup(email="nocred@example.com", password="strong-pass-123")
    service = UserCredentialService(session, encryption_key="cred-unit-test-key")

    status = service.get_exchange_credential_status(user=user, exchange="UPBIT")

    assert status["has_credentials"] is False
    assert status["is_valid"] is False
    assert status["access_key_masked"] is None


def test_set_exchange_credentials_validates_input():
    session = _session()
    user = AuthService(session).signup(email="badcred@example.com", password="strong-pass-123")
    service = UserCredentialService(session, encryption_key="cred-unit-test-key")

    with pytest.raises(CredentialValidationError, match="access_key is required"):
        service.set_exchange_credentials(
            user=user,
            exchange="UPBIT",
            access_key="",
            secret_key="secret-key-1234567890",
        )

    with pytest.raises(CredentialValidationError, match="only UPBIT is supported"):
        service.set_exchange_credentials(
            user=user,
            exchange="BINANCE",
            access_key="access-key-123456",
            secret_key="secret-key-1234567890",
        )

