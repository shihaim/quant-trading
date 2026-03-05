from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.auth.service import AuthConflictError, AuthCredentialsError, AuthService, AuthValidationError
from trader.data.db import Base


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_signup_and_login_roundtrip():
    session = _session()
    service = AuthService(session)

    user = service.signup(email="USER@example.com", password="strong-pass-123", display_name="  Alice  ")
    logged_in = service.login(email="user@example.com", password="strong-pass-123")

    assert user.email == "user@example.com"
    assert user.display_name == "Alice"
    assert user.password_hash != "strong-pass-123"
    assert logged_in.id == user.id


def test_signup_rejects_duplicate_email():
    session = _session()
    service = AuthService(session)
    service.signup(email="dupe@example.com", password="strong-pass-123")

    with pytest.raises(AuthConflictError, match="email already registered"):
        service.signup(email="DUPE@example.com", password="another-pass-123")


def test_signup_rejects_weak_password():
    session = _session()
    service = AuthService(session)

    with pytest.raises(AuthValidationError, match="at least 8"):
        service.signup(email="weak@example.com", password="123")


def test_login_rejects_invalid_password():
    session = _session()
    service = AuthService(session)
    service.signup(email="login@example.com", password="strong-pass-123")

    with pytest.raises(AuthCredentialsError, match="invalid credentials"):
        service.login(email="login@example.com", password="wrong-pass")

