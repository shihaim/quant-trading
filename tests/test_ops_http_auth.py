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
from trader.data.db import Base
from trader.data.models import DailyEquity, Order, TradeMetric, UserExchangeCredential


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
        assert payload["scope"]["mode"] == "legacy_single_bot_owner_bridge"
        assert payload["scope"]["user_id"] == 1
        assert payload["scope"]["owner_user_id"] == 1

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/pnl/daily?days=7&tz=UTC",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["days"] == 7
        assert len(payload["items"]) >= 1
        assert payload["scope"]["owner_user_id"] == 1

        status, payload = _request_json(
            port=server.server_port,
            method="GET",
            path="/api/me/metrics/trade?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert payload["count"] >= 1
        assert payload["scope"]["owner_user_id"] == 1

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
        assert status == 403
        assert payload["error"] == "no_data_scope"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        engine.dispose()
