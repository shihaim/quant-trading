from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.audit.service import ACTION_ADMIN_ACTION, ACTION_BOT_START, AuditLogReadQuery, AuditService
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


def test_audit_service_list_logs_supports_filters_pagination_and_redaction():
    session = _session()
    auth = AuthService(session)
    admin = auth.signup(email="admin@example.com", password="strong-pass-123")
    user_a = auth.signup(email="user-a@example.com", password="strong-pass-123")
    user_b = auth.signup(email="user-b@example.com", password="strong-pass-123")
    service = AuditService(session=session)
    base = datetime.now(timezone.utc) - timedelta(days=2)

    rows = [
        AuditLog(
            actor_user_id=admin.id,
            action=ACTION_ADMIN_ACTION,
            target_type="admin_route",
            target_id="/api/admin/users/runtime-summary",
            metadata_json=json.dumps({"outcome": "allowed", "target_user_id": user_a.id}),
            created_at=base + timedelta(minutes=1),
        ),
        AuditLog(
            actor_user_id=admin.id,
            action=ACTION_ADMIN_ACTION,
            target_type="admin_route",
            target_id="/api/admin/users/runtime-summary",
            metadata_json=json.dumps({"outcome": "forbidden", "target_user_id": user_b.id}),
            created_at=base + timedelta(minutes=2),
        ),
        AuditLog(
            actor_user_id=user_b.id,
            action="credential_update",
            target_type="user_exchange_credentials",
            target_id=f"{user_b.id}:UPBIT",
            metadata_json=json.dumps(
                {
                    "source": "/api/me/credentials/upbit",
                    "access_key": "should-not-leak",
                    "secret_key": "should-not-leak",
                }
            ),
            created_at=base + timedelta(minutes=3),
        ),
    ]
    session.add_all(rows)
    session.commit()

    result = service.list_logs(
        query=AuditLogReadQuery(
            from_utc=base,
            to_utc=base + timedelta(hours=1),
            limit=2,
            offset=0,
        )
    )
    assert result["pagination"]["returned"] == 2
    assert result["pagination"]["has_more"] is True
    assert result["items"][0]["action"] == "credential_update"
    assert result["items"][1]["action"] == ACTION_ADMIN_ACTION

    failure_only = service.list_logs(
        query=AuditLogReadQuery(
            from_utc=base,
            to_utc=base + timedelta(hours=1),
            success=False,
            limit=10,
            offset=0,
        )
    )
    assert len(failure_only["items"]) == 1
    assert failure_only["items"][0]["is_success"] is False
    assert failure_only["items"][0]["target_user_id"] == user_b.id

    target_b_only = service.list_logs(
        query=AuditLogReadQuery(
            from_utc=base,
            to_utc=base + timedelta(hours=1),
            target_user_id=user_b.id,
            limit=10,
            offset=0,
        )
    )
    assert len(target_b_only["items"]) == 2

    credential_row = next(item for item in result["items"] if item["action"] == "credential_update")
    assert credential_row["metadata"]["access_key"] == "[redacted]"
    assert credential_row["metadata"]["secret_key"] == "[redacted]"
