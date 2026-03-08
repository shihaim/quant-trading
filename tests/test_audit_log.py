from __future__ import annotations

import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.audit.service import ACTION_BOT_START, AuditService
from trader.auth.service import AuthService
from trader.data.db import Base
from trader.data.models import AuditLog


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_audit_service_records_user_action():
    session = _session()
    user = AuthService(session).signup(email="audit-user@example.com", password="strong-pass-123")

    row = AuditService(session=session).record_action(
        actor_user_id=user.id,
        action=ACTION_BOT_START,
        target_type="user_bot_runtime",
        target_id=str(user.id),
        metadata={"source": "/api/me/bot/start", "is_enabled": True},
    )

    loaded = session.execute(select(AuditLog).where(AuditLog.id == row.id)).scalar_one()
    assert loaded.actor_user_id == user.id
    assert loaded.action == ACTION_BOT_START
    assert loaded.target_type == "user_bot_runtime"
    assert loaded.target_id == str(user.id)
    assert json.loads(loaded.metadata_json)["source"] == "/api/me/bot/start"
