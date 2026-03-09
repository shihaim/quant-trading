from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from trader.auth.api_budget import ApiBudgetService, SCOPE_ME
from trader.auth.service import AuthService
from trader.data.db import Base
from trader.data.models import UserApiBudget


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_api_budget_consume_limits_within_window():
    session = _session()
    user = AuthService(session).signup(email="budget@example.com", password="strong-pass-123")
    service = ApiBudgetService(session=session)
    at = datetime(2026, 3, 8, 9, 0, 0, tzinfo=timezone.utc)

    first = service.consume(user_id=user.id, scope=SCOPE_ME, limit=2, window_seconds=60, now=at)
    second = service.consume(user_id=user.id, scope=SCOPE_ME, limit=2, window_seconds=60, now=at)
    third = service.consume(user_id=user.id, scope=SCOPE_ME, limit=2, window_seconds=60, now=at)

    assert first.is_limited is False
    assert second.is_limited is False
    assert third.is_limited is True
    assert third.request_count == 2
    assert third.blocked_count == 1


def test_api_budget_is_isolated_by_user():
    session = _session()
    user_a = AuthService(session).signup(email="budget-a@example.com", password="strong-pass-123")
    user_b = AuthService(session).signup(email="budget-b@example.com", password="strong-pass-123")
    service = ApiBudgetService(session=session)
    at = datetime(2026, 3, 8, 9, 0, 0, tzinfo=timezone.utc)

    service.consume(user_id=user_a.id, scope=SCOPE_ME, limit=1, window_seconds=60, now=at)
    blocked_a = service.consume(user_id=user_a.id, scope=SCOPE_ME, limit=1, window_seconds=60, now=at)
    allowed_b = service.consume(user_id=user_b.id, scope=SCOPE_ME, limit=1, window_seconds=60, now=at)

    assert blocked_a.is_limited is True
    assert allowed_b.is_limited is False


def test_api_budget_resets_on_new_window():
    session = _session()
    user = AuthService(session).signup(email="budget-reset@example.com", password="strong-pass-123")
    service = ApiBudgetService(session=session)
    at = datetime(2026, 3, 8, 9, 0, 0, tzinfo=timezone.utc)
    next_window = datetime(2026, 3, 8, 9, 1, 1, tzinfo=timezone.utc)

    service.consume(user_id=user.id, scope=SCOPE_ME, limit=1, window_seconds=60, now=at)
    blocked = service.consume(user_id=user.id, scope=SCOPE_ME, limit=1, window_seconds=60, now=at)
    reset = service.consume(user_id=user.id, scope=SCOPE_ME, limit=1, window_seconds=60, now=next_window)

    assert blocked.is_limited is True
    assert reset.is_limited is False
    assert reset.request_count == 1


def test_api_budget_recovers_when_concurrent_insert_hits_unique_violation(monkeypatch):
    session = _session()
    user = AuthService(session).signup(email="budget-race@example.com", password="strong-pass-123")
    at = datetime(2026, 3, 9, 10, 58, 57, tzinfo=timezone.utc)
    session.add(
        UserApiBudget(
            user_id=user.id,
            scope=SCOPE_ME,
            window_started_at=at,
            window_seconds=60,
            request_count=0,
            blocked_count=0,
        )
    )
    session.commit()

    service = ApiBudgetService(session=session)
    original_find_row = service._find_row
    original_commit = session.commit
    state = {"find_calls": 0, "commit_calls": 0}

    def flaky_find_row(*, user_id: int, scope: str):
        if state["find_calls"] == 0:
            state["find_calls"] += 1
            return None
        return original_find_row(user_id=user_id, scope=scope)

    def flaky_commit():
        if state["commit_calls"] == 0:
            state["commit_calls"] += 1
            raise IntegrityError(
                "INSERT INTO user_api_budget ...",
                {},
                Exception("duplicate key value violates unique constraint"),
            )
        return original_commit()

    monkeypatch.setattr(service, "_find_row", flaky_find_row)
    monkeypatch.setattr(session, "commit", flaky_commit)

    snapshot = service.consume(user_id=user.id, scope=SCOPE_ME, limit=5, window_seconds=60, now=at)

    assert snapshot.is_limited is False
    assert snapshot.request_count == 1
