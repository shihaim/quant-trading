from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.api.ops_http import create_ops_handler
from trader.audit.service import (
    ACTION_ADMIN_ACTION,
    ACTION_BOT_START,
    ACTION_BOT_STOP,
    ACTION_CREDENTIAL_UPDATE,
    ACTION_REQUEST_BUDGET_BLOCKED,
)
from trader.config.settings import settings
from trader.data.db import Base
from trader.data.models import (
    AuditLog,
    DailyEquity,
    Order,
    TradeMetric,
    User,
    UserApiBudget,
    UserBotRuntime,
    UserExchangeCredential,
    UserRiskGuard,
)

VALID_ACCESS_KEY = "A" * 40
VALID_SECRET_KEY = "S" * 40
SECOND_ACCESS_KEY = "B" * 40
SECOND_SECRET_KEY = "T" * 40
THIRD_ACCESS_KEY = "C" * 40
THIRD_SECRET_KEY = "U" * 40


def _request_json(
    *,
    port: int,
    method: str,
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    body = None
    req_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
        req_headers["Content-Length"] = str(len(body))
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, body=body, headers=req_headers)
    response = conn.getresponse()
    raw = response.read()
    conn.close()
    parsed = json.loads(raw.decode("utf-8")) if raw else {}
    return response.status, parsed


def _grant_admin_by_email(*, Session, email: str) -> None:
    with Session() as session:
        user = session.execute(select(User).where(User.email == email)).scalar_one()
        user.is_admin = True
        session.add(user)
        session.commit()


def test_auth_endpoints_support_signup_login_and_me(tmp_path):
    db_path = tmp_path / "ops-http-auth.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, payload = _request_json(port=server.server_port, method="GET", path="/api/me")
        assert status == 401
        assert payload["error"] == "unauthorized"
        status, payload = _request_json(port=server.server_port, method="GET", path="/api/me/orders")
        assert status == 401
        assert payload["error"] == "unauthorized"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={
                "email": "User@Example.com",
                "password": "strong-pass-123",
                "display_name": "V2 User",
            },
        )
        assert status == 201
        assert payload["token_type"] == "Bearer"
        assert payload["user"]["email"] == "user@example.com"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={
                "email": "user@example.com",
                "password": "strong-pass-123",
            },
        )
        assert status == 200
        token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["user"]["email"] == "user@example.com"
        assert payload["user"]["is_admin"] is False

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 403
        assert payload["error"] == "credentials_required"
        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/bot/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 403
        assert payload["error"] == "credentials_required"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/credentials/upbit",
            payload={
                "access_key": VALID_ACCESS_KEY,
                "secret_key": VALID_SECRET_KEY,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["has_credentials"] is True
        assert payload["is_valid"] is True
        assert payload["status_level"] == "connected"
        assert "access_key" not in payload
        assert "secret_key" not in payload
        assert VALID_SECRET_KEY not in str(payload)

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/credentials/upbit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["has_credentials"] is True
        assert payload["is_valid"] is True
        assert payload["status_level"] == "connected"
        assert payload["access_key_masked"] == "AAAA...AAAA"

        with Session() as session:
            row = session.execute(select(UserExchangeCredential)).scalar_one()
            assert row.access_key_encrypted != VALID_ACCESS_KEY
            assert row.secret_key_encrypted != VALID_SECRET_KEY

            order = Order(
                user_id=1,
                market="KRW-BTC",
                side="bid",
                ord_type="limit",
                requested_price=Decimal("100"),
                requested_volume=Decimal("1"),
                client_order_id="me-api-order-1",
                intent="ENTRY",
                state="OPEN",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(order)
            session.flush()
            session.add(
                TradeMetric(
                    order_id=order.id,
                    intent="ENTRY",
                    intended_price=Decimal("100"),
                    filled_vwap_price=Decimal("100.01"),
                    slippage_abs=Decimal("0.01"),
                    slippage_pct=Decimal("0.0001"),
                    fee_abs=Decimal("0.01"),
                    time_to_fill_ms=500,
                    partial_fill_count=1,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.add(
                DailyEquity(
                    user_id=1,
                    date_utc=datetime.now(timezone.utc).date(),
                    start_equity=Decimal("1000000"),
                    start_realized_pnl=Decimal("0"),
                    last_equity=Decimal("1000100"),
                    realized_pnl=Decimal("100"),
                    unrealized_pnl=Decimal("0"),
                    daily_pnl_abs=Decimal("100"),
                    daily_pnl_pct=Decimal("0.0001"),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/orders?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["count"] >= 1

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/pnl/daily?days=7&tz=UTC",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["days"] == 7
        assert len(payload["items"]) >= 1

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/metrics/trade?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["count"] >= 1

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["trade_mode"] == "PAPER"
        assert payload["bot"]["is_enabled"] is True
        assert payload["credential"]["has_credentials"] is True
        assert payload["credential"]["is_valid"] is True
        assert payload["today_pnl"]["daily_pnl_abs"] == 100.0
        assert payload["orders"]["open_count"] == 1
        assert payload["orders"]["needs_review_count"] == 0
        assert payload["last_updated_utc"] is not None
        assert "source" not in payload
        assert "scope" not in payload
        assert "user_id" not in payload

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/bot/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["source"] == "/api/me/bot/status"
        assert payload["is_enabled"] is True
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/bot/stop",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["source"] == "/api/me/bot/stop"
        assert payload["is_enabled"] is False
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/bot/start",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["source"] == "/api/me/bot/start"
        assert payload["is_enabled"] is True

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={
                "email": "user2@example.com",
                "password": "strong-pass-123",
            },
        )
        assert status == 201
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={
                "email": "user2@example.com",
                "password": "strong-pass-123",
            },
        )
        assert status == 200
        token2 = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/orders",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert status == 403
        assert payload["error"] == "credentials_required"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/overview",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert status == 200
        assert payload["credential"]["has_credentials"] is False
        assert payload["credential"]["status_level"] == "missing"
        assert payload["credential"]["next_action"] == "register_credentials"
        assert payload["orders"]["open_count"] == 0
        assert payload["today_pnl"]["daily_pnl_abs"] == 0.0

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/credentials/upbit",
            payload={
                "access_key": SECOND_ACCESS_KEY,
                "secret_key": SECOND_SECRET_KEY,
            },
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert status == 200
        assert payload["has_credentials"] is True

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/orders",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert status == 200
        assert payload["count"] == 0
        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/bot/status",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert status == 200
        assert payload["source"] == "/api/me/bot/status"
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/bot/start",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert status == 200
        assert payload["source"] == "/api/me/bot/start"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/bot/enable",
        )
        assert status == 410
        assert payload["error"] == "legacy_endpoint_retired"
        assert payload["replacement"] == "/api/me/bot/start"
        assert payload["source"] == "/api/bot/enable"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/bot/disable",
        )
        assert status == 410
        assert payload["error"] == "legacy_endpoint_retired"
        assert payload["replacement"] == "/api/me/bot/stop"
        assert payload["source"] == "/api/bot/disable"

        with Session() as session:
            user_id_1 = session.execute(select(User.id).where(User.email == "user@example.com")).scalar_one()
            user_id_2 = session.execute(select(User.id).where(User.email == "user2@example.com")).scalar_one()
            logs = session.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
            assert len(logs) == 5

            actions = [row.action for row in logs]
            assert actions == [
                ACTION_CREDENTIAL_UPDATE,
                ACTION_BOT_STOP,
                ACTION_BOT_START,
                ACTION_CREDENTIAL_UPDATE,
                ACTION_BOT_START,
            ]

            actor_ids = [row.actor_user_id for row in logs]
            assert actor_ids == [user_id_1, user_id_1, user_id_1, user_id_2, user_id_2]

            first_meta = json.loads(logs[0].metadata_json)
            assert first_meta["source"] == "/api/me/credentials/upbit"
            assert first_meta["exchange"] == "UPBIT"
            assert first_meta["has_credentials"] is True

            second_meta = json.loads(logs[1].metadata_json)
            assert second_meta["source"] == "/api/me/bot/stop"
            assert second_meta["is_enabled"] is False

            third_meta = json.loads(logs[2].metadata_json)
            assert third_meta["source"] == "/api/me/bot/start"
            assert third_meta["is_enabled"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_admin_ops_routes_require_admin_role(tmp_path, monkeypatch):
    db_path = tmp_path / "ops-http-admin-auth.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, payload = _request_json(port=server.server_port, method="GET", path="/api/ops/summary")
        assert status == 401
        assert payload["error"] == "unauthorized"

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        member_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 200
        assert payload["user"]["is_admin"] is False

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/ops/summary",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 403
        assert payload["error"] == "forbidden"
        assert payload["message"] == "admin_required"

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        _grant_admin_by_email(Session=Session, email="admin@example.com")
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        admin_token = payload["access_token"]
        assert payload["user"]["is_admin"] is True

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/ops/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 410
        assert payload["error"] == "legacy_endpoint_retired"
        assert payload["replacement"] == "/api/admin/users/runtime-summary"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/orders?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 410
        assert payload["error"] == "legacy_endpoint_retired"
        assert payload["replacement"] == "/api/admin/users/{user_id}/orders"

        with Session() as session:
            member_id = session.execute(select(User.id).where(User.email == "member@example.com")).scalar_one()
            admin_id = session.execute(select(User.id).where(User.email == "admin@example.com")).scalar_one()
            logs = session.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
            entries = []
            for row in logs:
                meta = json.loads(row.metadata_json)
                entries.append(
                    {
                        "action": row.action,
                        "actor_user_id": row.actor_user_id,
                        "source": meta.get("source"),
                        "outcome": meta.get("outcome"),
                        "replacement": meta.get("replacement"),
                    }
                )

            assert any(
                entry["action"] == ACTION_ADMIN_ACTION
                and entry["actor_user_id"] == member_id
                and entry["source"] == "/api/ops/summary"
                and entry["outcome"] == "forbidden"
                for entry in entries
            )
            assert any(
                entry["action"] == ACTION_ADMIN_ACTION
                and entry["actor_user_id"] == admin_id
                and entry["source"] in {"/api/ops/summary", "/api/orders"}
                and entry["outcome"] == "retired"
                for entry in entries
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_allowlist_email_does_not_grant_admin_without_db_role(tmp_path, monkeypatch):
    db_path = tmp_path / "ops-http-admin-allowlist-ignored.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 201

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        assert payload["user"]["is_admin"] is False
        token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/admin/users/runtime-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 403
        assert payload["error"] == "forbidden"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_admin_user_scoped_routes_enforce_admin_and_target_scope(tmp_path, monkeypatch):
    db_path = tmp_path / "ops-http-admin-user-scope.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        for email in ("admin@example.com", "member@example.com", "user-a@example.com", "user-b@example.com"):
            status, _ = _request_json(
                port=server.server_port,
                method="POST",
                path="/api/auth/signup",
                payload={"email": email, "password": "strong-pass-123"},
            )
            assert status == 201
        _grant_admin_by_email(Session=Session, email="admin@example.com")

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        admin_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        member_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "user-a@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        user_a_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "user-b@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        user_b_token = payload["access_token"]

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/credentials/upbit",
            payload={"access_key": VALID_ACCESS_KEY, "secret_key": VALID_SECRET_KEY},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert status == 200
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/credentials/upbit",
            payload={"access_key": SECOND_ACCESS_KEY, "secret_key": SECOND_SECRET_KEY},
            headers={"Authorization": f"Bearer {user_b_token}"},
        )
        assert status == 200

        with Session() as session:
            user_a_id = session.execute(select(User.id).where(User.email == "user-a@example.com")).scalar_one()
            user_b_id = session.execute(select(User.id).where(User.email == "user-b@example.com")).scalar_one()
            order_a = Order(
                user_id=user_a_id,
                market="KRW-BTC",
                side="bid",
                ord_type="limit",
                requested_price=Decimal("100"),
                requested_volume=Decimal("1"),
                client_order_id="admin-user-a-order-1",
                intent="ENTRY",
                state="OPEN",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            order_b = Order(
                user_id=user_b_id,
                market="KRW-ETH",
                side="ask",
                ord_type="limit",
                requested_price=Decimal("200"),
                requested_volume=Decimal("2"),
                client_order_id="admin-user-b-order-1",
                intent="EXIT",
                state="OPEN",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add_all([order_a, order_b])
            session.flush()
            session.add_all(
                [
                    TradeMetric(
                        order_id=order_a.id,
                        intent="ENTRY",
                        intended_price=Decimal("100"),
                        filled_vwap_price=Decimal("100.01"),
                        slippage_abs=Decimal("0.01"),
                        slippage_pct=Decimal("0.0001"),
                        fee_abs=Decimal("0.01"),
                        time_to_fill_ms=500,
                        partial_fill_count=1,
                        created_at=datetime.now(timezone.utc),
                    ),
                    TradeMetric(
                        order_id=order_b.id,
                        intent="EXIT",
                        intended_price=Decimal("200"),
                        filled_vwap_price=Decimal("199.95"),
                        slippage_abs=Decimal("0.05"),
                        slippage_pct=Decimal("0.00025"),
                        fee_abs=Decimal("0.02"),
                        time_to_fill_ms=300,
                        partial_fill_count=1,
                        created_at=datetime.now(timezone.utc),
                    ),
                    DailyEquity(
                        user_id=user_a_id,
                        date_utc=datetime.now(timezone.utc).date(),
                        start_equity=Decimal("1000000"),
                        start_realized_pnl=Decimal("0"),
                        last_equity=Decimal("1000100"),
                        realized_pnl=Decimal("100"),
                        unrealized_pnl=Decimal("0"),
                        daily_pnl_abs=Decimal("100"),
                        daily_pnl_pct=Decimal("0.0001"),
                        updated_at=datetime.now(timezone.utc),
                    ),
                    DailyEquity(
                        user_id=user_b_id,
                        date_utc=datetime.now(timezone.utc).date(),
                        start_equity=Decimal("2000000"),
                        start_realized_pnl=Decimal("0"),
                        last_equity=Decimal("1999900"),
                        realized_pnl=Decimal("-100"),
                        unrealized_pnl=Decimal("0"),
                        daily_pnl_abs=Decimal("-100"),
                        daily_pnl_pct=Decimal("-0.00005"),
                        updated_at=datetime.now(timezone.utc),
                    ),
                ]
            )
            session.commit()

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/users/{user_a_id}/orders?limit=10",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 403
        assert payload["error"] == "forbidden"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/users/{user_a_id}/orders?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["user_id"] == user_a_id
        assert payload["count"] == 1
        assert payload["items"][0]["market"] == "KRW-BTC"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/users/{user_b_id}/orders?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["user_id"] == user_b_id
        assert payload["count"] == 1
        assert payload["items"][0]["market"] == "KRW-ETH"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/users/{user_a_id}/pnl/daily?days=7&tz=UTC",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["user_id"] == user_a_id
        assert len(payload["items"]) == 1
        assert payload["items"][0]["realized_pnl"] == 100.0

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/users/{user_a_id}/metrics/trade?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["user_id"] == user_a_id
        assert payload["count"] == 1

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/users/{user_a_id}/credentials/upbit",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["user_id"] == user_a_id
        assert payload["has_credentials"] is True

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/users/{user_a_id}/bot/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["user_id"] == user_a_id
        assert payload["source"].endswith("/bot/status")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_admin_can_invalidate_user_sessions_with_token_version_bump(tmp_path, monkeypatch):
    db_path = tmp_path / "ops-http-admin-session-invalidate.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        _grant_admin_by_email(Session=Session, email="admin@example.com")
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 201

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        admin_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        member_token = payload["access_token"]

        with Session() as session:
            member_id = session.execute(select(User.id).where(User.email == "member@example.com")).scalar_one()

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path=f"/api/admin/users/{member_id}/sessions/invalidate",
            payload={"reason": "role_changed"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 403
        assert payload["error"] == "forbidden"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path=f"/api/admin/users/{member_id}/sessions/invalidate",
            payload={"reason": "role_changed"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["user_id"] == member_id
        assert payload["invalidated_before_version"] == 1
        assert payload["token_version"] == 2
        assert payload["reason"] == "role_changed"
        assert payload["source"] == f"/api/admin/users/{member_id}/sessions/invalidate"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 401
        assert payload["error"] == "unauthorized"
        assert payload["message"] == "session_revoked"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        fresh_member_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {fresh_member_token}"},
        )
        assert status == 200
        assert payload["user"]["email"] == "member@example.com"

        with Session() as session:
            member = session.execute(select(User).where(User.email == "member@example.com")).scalar_one()
            assert member.token_version == 2
            logs = session.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
            assert len(logs) == 2
            assert logs[0].action == ACTION_ADMIN_ACTION
            first_meta = json.loads(logs[0].metadata_json)
            assert first_meta["source"] == f"/api/admin/users/{member_id}/sessions/invalidate"
            assert first_meta["outcome"] == "forbidden"
            assert first_meta["method"] == "POST"
            second_meta = json.loads(logs[1].metadata_json)
            assert second_meta["source"] == f"/api/admin/users/{member_id}/sessions/invalidate"
            assert second_meta["outcome"] == "allowed"
            assert second_meta["target_user_id"] == member_id
            assert second_meta["reason"] == "role_changed"
            assert second_meta["token_version_before"] == 1
            assert second_meta["token_version_after"] == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_admin_role_update_uses_db_role_and_revokes_existing_session(tmp_path, monkeypatch):
    db_path = tmp_path / "ops-http-admin-role-update.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        for email in ("db-admin@example.com", "member@example.com"):
            status, _ = _request_json(
                port=server.server_port,
                method="POST",
                path="/api/auth/signup",
                payload={"email": email, "password": "strong-pass-123"},
            )
            assert status == 201

        with Session() as session:
            admin_user = session.execute(select(User).where(User.email == "db-admin@example.com")).scalar_one()
            admin_user.is_admin = True
            session.add(admin_user)
            session.commit()

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "db-admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        assert payload["user"]["is_admin"] is True
        admin_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        assert payload["user"]["is_admin"] is False
        member_token_before = payload["access_token"]

        with Session() as session:
            member_id = session.execute(select(User.id).where(User.email == "member@example.com")).scalar_one()

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path=f"/api/admin/users/{member_id}/role",
            payload={"role": "admin"},
            headers={"Authorization": f"Bearer {member_token_before}"},
        )
        assert status == 403
        assert payload["error"] == "forbidden"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path=f"/api/admin/users/{member_id}/role",
            payload={"role": "admin"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["user_id"] == member_id
        assert payload["is_admin"] is True
        assert payload["changed"] is True
        assert payload["invalidated_before_version"] == 1
        assert payload["token_version"] == 2

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {member_token_before}"},
        )
        assert status == 401
        assert payload["message"] == "session_revoked"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        assert payload["user"]["is_admin"] is True
        member_token_after = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/admin/users/runtime-summary",
            headers={"Authorization": f"Bearer {member_token_after}"},
        )
        assert status == 200
        assert payload["source"] == "/api/admin/users/runtime-summary"

        with Session() as session:
            logs = session.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
            role_logs = [
                log
                for log in logs
                if json.loads(log.metadata_json).get("source") == f"/api/admin/users/{member_id}/role"
            ]
            assert len(role_logs) == 2
            forbidden_meta = json.loads(role_logs[0].metadata_json)
            assert forbidden_meta["source"] == f"/api/admin/users/{member_id}/role"
            assert forbidden_meta["outcome"] == "forbidden"
            allowed_meta = json.loads(role_logs[1].metadata_json)
            assert role_logs[1].actor_user_id is not None
            assert allowed_meta["source"] == f"/api/admin/users/{member_id}/role"
            assert allowed_meta["outcome"] == "allowed"
            assert allowed_meta["target_user_id"] == member_id
            assert allowed_meta["role_before"] == "member"
            assert allowed_meta["role_after"] == "admin"
            assert allowed_meta["changed"] is True
            assert allowed_meta["token_version_before"] == 1
            assert allowed_meta["token_version_after"] == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_admin_alias_routes_retire_and_key_rotation_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ops_api_credentials_encryption_key", "ops-key-v1")
    monkeypatch.setattr(settings, "ops_api_credentials_active_key_version", "v1")
    monkeypatch.setattr(settings, "ops_api_credentials_keyring_json", json.dumps({"v1": "ops-key-v1", "v2": "ops-key-v2"}))

    db_path = tmp_path / "ops-http-admin-alias.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        _grant_admin_by_email(Session=Session, email="admin@example.com")
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        admin_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/admin/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 410
        assert payload["error"] == "legacy_endpoint_retired"
        assert payload["replacement"] == "/api/admin/users/runtime-summary"

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        member_token = payload["access_token"]
        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/admin/summary",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 403
        assert payload["error"] == "forbidden"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/credentials/upbit",
            payload={"access_key": VALID_ACCESS_KEY, "secret_key": VALID_SECRET_KEY},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 200
        assert payload["is_valid"] is True

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/ops/credentials/rotate",
            payload={"target_key_version": "v2", "dry_run": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 410
        assert payload["error"] == "legacy_endpoint_retired"
        assert payload["replacement"] == "/api/admin/credentials/rotate"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/admin/credentials/rotate",
            payload={"target_key_version": "v2", "dry_run": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["target_key_version"] == "v2"
        assert payload["rotated"] >= 1
        assert payload["failed"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_admin_user_runtime_summary_endpoint_enforces_boundary_and_reflects_state(tmp_path, monkeypatch):
    db_path = tmp_path / "ops-http-admin-runtime-summary.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        _grant_admin_by_email(Session=Session, email="admin@example.com")
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        admin_token = payload["access_token"]

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "user-a@example.com", "password": "strong-pass-123", "display_name": "User A"},
        )
        assert status == 201
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "user-a@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        user_a_token = payload["access_token"]

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "user-b@example.com", "password": "strong-pass-123", "display_name": "User B"},
        )
        assert status == 201
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "user-b@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        user_b_token = payload["access_token"]

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/credentials/upbit",
            payload={"access_key": THIRD_ACCESS_KEY, "secret_key": THIRD_SECRET_KEY},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert status == 200
        assert payload["is_valid"] is True

        with Session() as session:
            user_a_id = session.execute(select(User.id).where(User.email == "user-a@example.com")).scalar_one()
            user_b_id = session.execute(select(User.id).where(User.email == "user-b@example.com")).scalar_one()
            now = datetime.now(timezone.utc)

            session.add(
                UserBotRuntime(
                    user_id=user_b_id,
                    is_enabled=False,
                    status="DEGRADED",
                    last_tick_at=now,
                    last_error="risk_guard:manual_halt",
                    consecutive_failures=3,
                    updated_at=now,
                )
            )
            session.add(
                UserRiskGuard(
                    user_id=user_b_id,
                    manual_halt=True,
                    emergency_kill_switch=False,
                    reason="operator-halt",
                    updated_by_user_id=user_b_id,
                    updated_at=now,
                )
            )
            session.add(
                UserApiBudget(
                    user_id=user_b_id,
                    scope="ME",
                    window_started_at=now,
                    window_seconds=60,
                    request_count=8,
                    blocked_count=2,
                    updated_at=now,
                )
            )
            session.add(
                Order(
                    user_id=user_a_id,
                    market="KRW-BTC",
                    side="bid",
                    ord_type="limit",
                    requested_price=Decimal("100"),
                    requested_volume=Decimal("1"),
                    client_order_id="runtime-summary-user-a-order",
                    intent="ENTRY",
                    state="OPEN",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                Order(
                    user_id=user_b_id,
                    market="KRW-ETH",
                    side="ask",
                    ord_type="limit",
                    requested_price=Decimal("200"),
                    requested_volume=Decimal("2"),
                    client_order_id="runtime-summary-user-b-order",
                    intent="EXIT",
                    state="ERROR_NEEDS_REVIEW",
                    error_class="RiskGuardError",
                    last_error="risk guard halted",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                AuditLog(
                    actor_user_id=user_b_id,
                    action=ACTION_BOT_STOP,
                    target_type="user_bot_runtime",
                    target_id=str(user_b_id),
                    metadata_json=json.dumps({"source": "test"}),
                    created_at=now,
                )
            )
            session.commit()

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/admin/users/runtime-summary?limit=50",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert status == 403
        assert payload["error"] == "forbidden"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/admin/users/runtime-summary?limit=50",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["source"] == "/api/admin/users/runtime-summary"
        assert payload["count"] >= 3

        item_by_email = {item["email"]: item for item in payload["items"]}
        assert "user-a@example.com" in item_by_email
        assert "user-b@example.com" in item_by_email

        user_a_item = item_by_email["user-a@example.com"]
        assert user_a_item["credential"]["has_credentials"] is True
        assert user_a_item["credential"]["is_valid"] is True
        assert user_a_item["flags"]["is_credential_invalid"] is False

        user_b_item = item_by_email["user-b@example.com"]
        assert user_b_item["bot"]["status"] == "HALTED"
        assert user_b_item["halt"]["reason"] == "manual_halt"
        assert user_b_item["budget"]["blocked_count"] == 2
        assert user_b_item["flags"]["is_budget_blocked"] is True
        assert user_b_item["flags"]["is_halted"] is True
        assert user_b_item["flags"]["is_credential_invalid"] is True
        assert user_b_item["activity"]["recent_order_at_utc"] is not None
        assert user_b_item["activity"]["recent_audit_at_utc"] is not None
        assert user_b_item["activity"]["recent_error_at_utc"] is not None
        event_by_kind = {event["kind"]: event for event in user_b_item["events"]}
        assert set(event_by_kind) == {"halt", "credential_issue", "order_review", "runtime_error"}
        assert event_by_kind["halt"]["title"] == "User runtime halted"
        assert event_by_kind["halt"]["detail"]["target_user_id"] == user_b_id
        assert event_by_kind["credential_issue"]["detail"]["has_credentials"] is False
        assert event_by_kind["order_review"]["message"] == "1 order requires manual review."
        assert event_by_kind["runtime_error"]["detail"]["last_error"] == "risk_guard:manual_halt"

        # Critical user (budget blocked + halted + invalid credential) should be prioritized.
        assert payload["items"][0]["email"] == "user-b@example.com"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_admin_audit_logs_endpoint_supports_filters_pagination_and_admin_boundary(tmp_path, monkeypatch):
    db_path = tmp_path / "ops-http-admin-audit-logs.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        _grant_admin_by_email(Session=Session, email="admin@example.com")
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "admin@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        admin_token = payload["access_token"]

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "member@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        member_token = payload["access_token"]

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "user-a@example.com", "password": "strong-pass-123"},
        )
        assert status == 201

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "user-b@example.com", "password": "strong-pass-123"},
        )
        assert status == 201

        with Session() as session:
            admin_id = session.execute(select(User.id).where(User.email == "admin@example.com")).scalar_one()
            user_a_id = session.execute(select(User.id).where(User.email == "user-a@example.com")).scalar_one()
            user_b_id = session.execute(select(User.id).where(User.email == "user-b@example.com")).scalar_one()
            base = datetime.now(timezone.utc) - timedelta(days=2)

            session.add_all(
                [
                    AuditLog(
                        actor_user_id=admin_id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=f"/api/admin/users/{user_a_id}/orders",
                        metadata_json=json.dumps(
                            {
                                "source": "seed-audit",
                                "outcome": "allowed",
                                "target_user_id": user_a_id,
                            }
                        ),
                        created_at=base + timedelta(minutes=1),
                    ),
                    AuditLog(
                        actor_user_id=admin_id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=f"/api/admin/users/{user_b_id}/orders",
                        metadata_json=json.dumps(
                            {
                                "source": "seed-audit",
                                "outcome": "forbidden",
                                "target_user_id": user_b_id,
                            }
                        ),
                        created_at=base + timedelta(minutes=2),
                    ),
                    AuditLog(
                        actor_user_id=user_b_id,
                        action=ACTION_CREDENTIAL_UPDATE,
                        target_type="user_exchange_credentials",
                        target_id=f"{user_b_id}:UPBIT",
                        metadata_json=json.dumps(
                            {
                                "source": "/api/me/credentials/upbit",
                                "outcome": "success",
                                "access_key": "should-not-leak",
                                "secret_key": "should-not-leak",
                            }
                        ),
                        created_at=base + timedelta(minutes=3),
                    ),
                ]
            )
            session.commit()

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/admin/audit/logs?limit=2",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 403
        assert payload["error"] == "forbidden"

        from_utc = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat().replace("+00:00", "Z")
        to_utc = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/audit/logs?limit=2&offset=0&from={from_utc}&to={to_utc}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["pagination"]["returned"] == 2
        assert payload["pagination"]["has_more"] is True
        assert payload["items"][0]["action"] == ACTION_CREDENTIAL_UPDATE
        assert payload["items"][1]["action"] == ACTION_ADMIN_ACTION

        credential_item = next(item for item in payload["items"] if item["action"] == ACTION_CREDENTIAL_UPDATE)
        assert credential_item["metadata"]["access_key"] == "[redacted]"
        assert credential_item["metadata"]["secret_key"] == "[redacted]"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path=f"/api/admin/audit/logs?target_user_id={user_b_id}&result=failure&from={from_utc}&to={to_utc}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert payload["pagination"]["returned"] == 1
        assert payload["items"][0]["target_user_id"] == user_b_id
        assert payload["items"][0]["is_success"] is False

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/admin/audit/logs?from=2026-01-01T00:00:00Z&to=2026-03-15T00:00:00Z",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 400
        assert payload["error"] == "invalid_date_range"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_me_request_budget_isolation_under_throttling(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ops_api_budget_window_seconds", 60)
    monkeypatch.setattr(settings, "ops_api_budget_me_limit", 2)

    db_path = tmp_path / "ops-http-budget.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    handler_cls = create_ops_handler(
        session_factory=Session,
        trade_mode="PAPER",
        allow_origin="*",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "user-a@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "user-a@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        token_a = payload["access_token"]

        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/signup",
            payload={"email": "user-b@example.com", "password": "strong-pass-123"},
        )
        assert status == 201
        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/auth/login",
            payload={"email": "user-b@example.com", "password": "strong-pass-123"},
        )
        assert status == 200
        token_b = payload["access_token"]

        status, _ = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert status == 200
        status, _ = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert status == 200
        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert status == 429
        assert payload["error"] == "rate_limited"
        assert payload["budget"]["scope"] == "me"
        assert payload["budget"]["is_limited"] is True

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert status == 200
        assert payload["user"]["email"] == "user-b@example.com"

        with Session() as session:
            user_a_id = session.execute(select(User.id).where(User.email == "user-a@example.com")).scalar_one()
            logs = session.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
            budget_logs = [row for row in logs if row.action == ACTION_REQUEST_BUDGET_BLOCKED]
            assert len(budget_logs) == 1
            assert budget_logs[0].actor_user_id == user_a_id
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()
