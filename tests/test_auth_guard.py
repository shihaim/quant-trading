from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.auth.guard import authenticate_request, extract_bearer_token
from trader.auth.service import AuthService
from trader.auth.tokens import issue_access_token
from trader.data.db import Base


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_extract_bearer_token_reads_authorization_header():
    assert extract_bearer_token("Bearer abc.def") == "abc.def"
    assert extract_bearer_token("Basic abc") is None
    assert extract_bearer_token(None) is None


def test_authenticate_request_returns_user_on_valid_token():
    session = _session()
    user = AuthService(session).signup(email="guard@example.com", password="strong-pass-123")
    token = issue_access_token(user_id=user.id, secret="guard-secret", ttl_seconds=60)

    result = authenticate_request(
        session=session,
        authorization_header=f"Bearer {token}",
        secret="guard-secret",
    )

    assert result.error is None
    assert result.user is not None
    assert result.user.id == user.id


def test_authenticate_request_rejects_invalid_or_missing_token():
    session = _session()
    AuthService(session).signup(email="guard2@example.com", password="strong-pass-123")

    missing = authenticate_request(
        session=session,
        authorization_header=None,
        secret="guard-secret",
    )
    invalid = authenticate_request(
        session=session,
        authorization_header="Bearer malformed-token",
        secret="guard-secret",
    )

    assert missing.error == "missing_token"
    assert invalid.error == "invalid_token"
