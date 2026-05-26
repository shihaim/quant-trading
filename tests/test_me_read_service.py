from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.auth.credentials import UserCredentialService
from trader.auth.service import AuthService
from trader.config.config_repo import ConfigRepo
from trader.data.db import Base
from trader.data.models import DailyEquity, Order, TradeMetric, UserBotRuntime
from trader.me.read_service import MeReadService, UserScopeError

VALID_ACCESS_KEY = "A" * 40
VALID_SECRET_KEY = "S" * 40
SECOND_ACCESS_KEY = "B" * 40
SECOND_SECRET_KEY = "T" * 40
THIRD_ACCESS_KEY = "C" * 40
THIRD_SECRET_KEY = "U" * 40


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def _seed_user_rows(session, *, user_id: int) -> None:
    order = Order(
        user_id=user_id,
        market="KRW-BTC",
        side="bid",
        ord_type="limit",
        requested_price=Decimal("100"),
        requested_volume=Decimal("1"),
        client_order_id="me-service-order-1",
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
            user_id=user_id,
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


def test_me_read_service_returns_current_user_scope_data():
    session = _session()
    owner = AuthService(session).signup(email="owner@example.com", password="strong-pass-123")
    UserCredentialService(session, encryption_key="me-read-key").set_exchange_credentials(
        user=owner,
        exchange="UPBIT",
        access_key=VALID_ACCESS_KEY,
        secret_key=VALID_SECRET_KEY,
    )
    _seed_user_rows(session, user_id=owner.id)

    service = MeReadService(session=session, trade_mode="PAPER", encryption_key="me-read-key")
    orders = service.list_orders(user=owner, limit=10)
    pnl = service.get_pnl_daily(user=owner, days=7, tz="UTC")
    metrics = service.list_trade_metrics(user=owner, limit=10)
    status = service.get_bot_status(user=owner)
    stop_result = service.stop_bot(user=owner)
    start_result = service.start_bot(user=owner)

    assert orders["count"] >= 1
    assert pnl["days"] == 7
    assert metrics["count"] >= 1
    assert "scope" not in orders
    assert status["source"] == "/api/me/bot/status"
    assert stop_result["source"] == "/api/me/bot/stop"
    assert stop_result["is_enabled"] is False
    assert start_result["source"] == "/api/me/bot/start"
    assert start_result["is_enabled"] is True


def test_me_read_service_scopes_data_per_user_without_bridge_error():
    session = _session()
    owner = AuthService(session).signup(email="owner2@example.com", password="strong-pass-123")
    other = AuthService(session).signup(email="other2@example.com", password="strong-pass-123")
    credential_service = UserCredentialService(session, encryption_key="me-read-key")
    credential_service.set_exchange_credentials(
        user=owner,
        exchange="UPBIT",
        access_key=VALID_ACCESS_KEY,
        secret_key=VALID_SECRET_KEY,
    )
    credential_service.set_exchange_credentials(
        user=other,
        exchange="UPBIT",
        access_key=SECOND_ACCESS_KEY,
        secret_key=SECOND_SECRET_KEY,
    )
    _seed_user_rows(session, user_id=owner.id)

    service = MeReadService(session=session, trade_mode="PAPER", encryption_key="me-read-key")
    other_orders = service.list_orders(user=other, limit=10)
    other_pnl = service.get_pnl_daily(user=other, days=7, tz="UTC")
    other_metrics = service.list_trade_metrics(user=other, limit=10)
    other_status = service.get_bot_status(user=other)
    other_start = service.start_bot(user=other)

    assert other_orders["count"] == 0
    assert other_pnl["days"] == 7
    assert other_pnl["items"] == []
    assert other_metrics["count"] == 0
    assert other_status["source"] == "/api/me/bot/status"
    assert other_start["source"] == "/api/me/bot/start"
    assert other_start["is_enabled"] is True


def test_me_bot_stop_isolated_per_user_runtime():
    session = _session()
    user_a = AuthService(session).signup(email="user-a@example.com", password="strong-pass-123")
    user_b = AuthService(session).signup(email="user-b@example.com", password="strong-pass-123")
    credential_service = UserCredentialService(session, encryption_key="me-read-key")
    credential_service.set_exchange_credentials(
        user=user_a,
        exchange="UPBIT",
        access_key=VALID_ACCESS_KEY,
        secret_key=VALID_SECRET_KEY,
    )
    credential_service.set_exchange_credentials(
        user=user_b,
        exchange="UPBIT",
        access_key=SECOND_ACCESS_KEY,
        secret_key=SECOND_SECRET_KEY,
    )

    service = MeReadService(session=session, trade_mode="PAPER", encryption_key="me-read-key")
    service.start_bot(user=user_a)
    service.start_bot(user=user_b)
    stop_a = service.stop_bot(user=user_a)

    repo = ConfigRepo(session)
    state_a = repo.get_runtime_state(user_a.id)
    state_b = repo.get_runtime_state(user_b.id)

    assert stop_a["source"] == "/api/me/bot/stop"
    assert stop_a["is_enabled"] is False
    assert state_a.is_enabled is False
    assert state_b.is_enabled is True


def test_me_bot_start_blocks_during_cooldown():
    session = _session()
    user = AuthService(session).signup(email="cooldown@example.com", password="strong-pass-123")
    UserCredentialService(session, encryption_key="me-read-key").set_exchange_credentials(
        user=user,
        exchange="UPBIT",
        access_key=THIRD_ACCESS_KEY,
        secret_key=THIRD_SECRET_KEY,
    )
    runtime = session.execute(
        select(UserBotRuntime).where(UserBotRuntime.user_id == user.id)
    ).scalar_one_or_none()
    if runtime is None:
        runtime = UserBotRuntime(user_id=user.id)
        session.add(runtime)
        session.flush()
    runtime.is_enabled = False
    runtime.status = "HALTED"
    runtime.halt_reason = "daily_loss_limit"
    runtime.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=2)
    runtime.halted_at = datetime.now(timezone.utc)
    session.commit()

    service = MeReadService(session=session, trade_mode="PAPER", encryption_key="me-read-key")
    try:
        service.start_bot(user=user)
        assert False, "expected cooldown_active"
    except UserScopeError as exc:
        assert exc.code == "cooldown_active"
