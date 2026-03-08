from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
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
from trader.data.models import AuditLog, DailyEquity, Order, TradeMetric, User, UserExchangeCredential


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
                "access_key": "access-key-123456",
                "secret_key": "secret-key-1234567890",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["has_credentials"] is True
        assert payload["is_valid"] is True
        assert "access_key" not in payload
        assert "secret_key" not in payload

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/credentials/upbit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["has_credentials"] is True
        assert payload["is_valid"] is True
        assert payload["access_key_masked"].startswith("acce...")

        with Session() as session:
            row = session.execute(select(UserExchangeCredential)).scalar_one()
            assert row.access_key_encrypted != "access-key-123456"
            assert row.secret_key_encrypted != "secret-key-1234567890"

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
            method="POST",
            path="/api/me/credentials/upbit",
            payload={
                "access_key": "access-key-654321",
                "secret_key": "secret-key-0987654321",
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
        assert status == 404
        assert payload["error"] == "not_found"

        status, payload = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/bot/disable",
        )
        assert status == 404
        assert payload["error"] == "not_found"

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
    monkeypatch.setattr(settings, "ops_api_admin_emails", ["admin@example.com"])

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
        assert status == 200
        assert payload["trade_mode"] == "PAPER"

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/orders?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert status == 200
        assert "count" in payload

        with Session() as session:
            member_id = session.execute(select(User.id).where(User.email == "member@example.com")).scalar_one()
            admin_id = session.execute(select(User.id).where(User.email == "admin@example.com")).scalar_one()
            logs = session.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
            assert len(logs) == 3
            assert [row.action for row in logs] == [ACTION_ADMIN_ACTION, ACTION_ADMIN_ACTION, ACTION_ADMIN_ACTION]
            assert [row.actor_user_id for row in logs] == [member_id, admin_id, admin_id]

            first_meta = json.loads(logs[0].metadata_json)
            assert first_meta["source"] == "/api/ops/summary"
            assert first_meta["outcome"] == "forbidden"

            second_meta = json.loads(logs[1].metadata_json)
            assert second_meta["source"] == "/api/ops/summary"
            assert second_meta["outcome"] == "allowed"

            third_meta = json.loads(logs[2].metadata_json)
            assert third_meta["source"] == "/api/orders"
            assert third_meta["outcome"] == "allowed"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()


def test_admin_user_scoped_routes_enforce_admin_and_target_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ops_api_admin_emails", ["admin@example.com"])

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
            payload={"access_key": "access-key-a12345", "secret_key": "secret-key-a1234567890"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert status == 200
        status, _ = _request_json(
            port=server.server_port,
            method="POST",
            path="/api/me/credentials/upbit",
            payload={"access_key": "access-key-b12345", "secret_key": "secret-key-b1234567890"},
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


def test_admin_alias_routes_and_key_rotation_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ops_api_admin_emails", ["admin@example.com"])
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
        assert status == 200
        assert payload["trade_mode"] == "PAPER"
        assert payload["api_budget"]["scope"] == "admin"

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
            payload={"access_key": "access-key-123456", "secret_key": "secret-key-1234567890"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert status == 200
        assert payload["is_valid"] is True

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
