from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.auth.crypto import encrypt_secret
from trader.config.config_repo import RuntimeConfig
from trader.data.db import Base
from trader.data.models import User, UserBotRuntime, UserExchangeCredential, UserRiskGuard
from trader.trading import scheduler as scheduler_module
from trader.trading.scheduler import MultiUserTradingScheduler, TradingScheduler


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session


def _cfg() -> RuntimeConfig:
    return RuntimeConfig(
        is_enabled=True,
        timeframe="15m",
        markets=["KRW-BTC"],
        max_daily_loss_pct=Decimal("0.02"),
        max_total_exposure_pct=Decimal("0.30"),
        max_per_market_exposure_pct=Decimal("0.10"),
    )


def test_trading_scheduler_requires_explicit_user_id(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "PAPER")
    Session = _session_factory()
    with Session() as session:
        with pytest.raises(ValueError, match="user_id_required"):
            TradingScheduler(session=session)


def test_trading_scheduler_accepts_explicit_user_id(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "PAPER")
    Session = _session_factory()
    with Session() as session:
        scheduler = TradingScheduler(session=session, user_id=3)

        assert scheduler.user_id == 3
        scheduler.upbit.close()


def test_list_active_user_ids_requires_runtime_enabled_and_credentials(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "TEST")
    Session = _session_factory()
    with Session() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="hash"),
                User(id=2, email="u2@example.com", password_hash="hash"),
                User(id=3, email="u3@example.com", password_hash="hash"),
            ]
        )
        session.flush()
        session.add_all(
            [
                UserExchangeCredential(
                    user_id=1,
                    exchange="UPBIT",
                    access_key_encrypted="enc-a",
                    secret_key_encrypted="enc-b",
                    access_key_masked="****",
                    access_key_fingerprint="fp1",
                ),
                UserExchangeCredential(
                    user_id=2,
                    exchange="UPBIT",
                    access_key_encrypted="enc-c",
                    secret_key_encrypted="enc-d",
                    access_key_masked="****",
                    access_key_fingerprint="fp2",
                ),
                UserBotRuntime(user_id=2, is_enabled=False, status="IDLE", consecutive_failures=0),
            ]
        )
        session.commit()

    scheduler = MultiUserTradingScheduler(session_factory=Session)
    assert scheduler._list_active_user_ids() == [1]


def test_ensure_state_logs_user_schedule(monkeypatch, caplog):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "PAPER")
    Session = _session_factory()
    with Session() as session:
        session.add(User(id=1, email="u1@example.com", password_hash="hash"))
        session.commit()

    scheduler = MultiUserTradingScheduler(session_factory=Session)
    now = datetime(2026, 3, 8, 0, 0, tzinfo=timezone.utc)

    with caplog.at_level(logging.INFO, logger="trader.trading.scheduler"):
        state = scheduler._ensure_state(1, now)
        scheduler._ensure_state(1, now + timedelta(seconds=20))

    messages = "\n".join(caplog.messages)
    assert "multi_user_scheduler_user_scheduled user_id=1" in messages
    assert "multi_user_scheduler_user_waiting user_id=1" in messages
    assert state.next_run_at.isoformat() in messages


def test_run_user_tick_isolated_failure_updates_runtime(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "PAPER")
    Session = _session_factory()
    with Session() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="hash"),
                User(id=2, email="u2@example.com", password_hash="hash"),
            ]
        )
        session.commit()

    class _DummyUpbit:
        def close(self) -> None:
            return None

    class _WorkerStub:
        def __init__(self, session, *, user_id: int, access_key=None, secret_key=None, notifier=None):
            self.user_id = user_id
            self.upbit = _DummyUpbit()

        def _run_once(self, cfg: RuntimeConfig) -> None:
            if self.user_id == 1:
                raise RuntimeError("user-1-failure")

    monkeypatch.setattr(scheduler_module, "TradingScheduler", _WorkerStub)

    scheduler = MultiUserTradingScheduler(session_factory=Session)
    now = datetime(2026, 3, 8, 0, 0, tzinfo=timezone.utc)
    cfg = _cfg()
    scheduler._run_user_tick(1, cfg, now)
    scheduler._run_user_tick(2, cfg, now)

    with Session() as session:
        row1 = session.execute(select(UserBotRuntime).where(UserBotRuntime.user_id == 1)).scalar_one()
        row2 = session.execute(select(UserBotRuntime).where(UserBotRuntime.user_id == 2)).scalar_one()

    assert row1.status == "ERROR"
    assert row1.consecutive_failures == 1
    assert "user-1-failure" in (row1.last_error or "")
    assert row2.status == "IDLE"
    assert row2.consecutive_failures == 0
    assert row2.last_error is None


def test_load_user_credentials_uses_encrypted_store(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "TEST")
    monkeypatch.setattr(scheduler_module.settings, "ops_api_credentials_encryption_key", "test-v3-key")
    Session = _session_factory()
    with Session() as session:
        session.add(User(id=1, email="u1@example.com", password_hash="hash"))
        session.flush()
        session.add(
            UserExchangeCredential(
                user_id=1,
                exchange="UPBIT",
                access_key_encrypted=encrypt_secret("access-123456", encryption_key="test-v3-key"),
                secret_key_encrypted=encrypt_secret("secret-1234567890", encryption_key="test-v3-key"),
                access_key_masked="acce...3456",
                access_key_fingerprint="fp",
            )
        )
        session.commit()

    scheduler = MultiUserTradingScheduler(session_factory=Session)
    access_key, secret_key = scheduler._load_user_credentials(1)
    assert access_key == "access-123456"
    assert secret_key == "secret-1234567890"


def test_load_user_credentials_supports_key_version_and_keyring(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "TEST")
    monkeypatch.setattr(scheduler_module.settings, "ops_api_credentials_encryption_key", "legacy-v1-key")
    monkeypatch.setattr(scheduler_module.settings, "ops_api_credentials_active_key_version", "v2")
    monkeypatch.setattr(
        scheduler_module.settings,
        "ops_api_credentials_keyring_json",
        '{"v1":"legacy-v1-key","v2":"next-v2-key"}',
    )
    Session = _session_factory()
    with Session() as session:
        session.add(User(id=1, email="u1@example.com", password_hash="hash"))
        session.flush()
        session.add(
            UserExchangeCredential(
                user_id=1,
                exchange="UPBIT",
                access_key_encrypted=encrypt_secret("access-v2-123456", encryption_key="next-v2-key"),
                secret_key_encrypted=encrypt_secret("secret-v2-1234567890", encryption_key="next-v2-key"),
                key_version="v2",
                access_key_masked="acce...3456",
                access_key_fingerprint="fp",
            )
        )
        session.commit()

    scheduler = MultiUserTradingScheduler(session_factory=Session)
    access_key, secret_key = scheduler._load_user_credentials(1)
    assert access_key == "access-v2-123456"
    assert secret_key == "secret-v2-1234567890"


def test_list_active_user_ids_excludes_manual_halt_user(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "TEST")
    Session = _session_factory()
    with Session() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="hash"),
                User(id=2, email="u2@example.com", password_hash="hash"),
            ]
        )
        session.flush()
        session.add_all(
            [
                UserExchangeCredential(
                    user_id=1,
                    exchange="UPBIT",
                    access_key_encrypted="enc-a",
                    secret_key_encrypted="enc-b",
                    access_key_masked="****",
                    access_key_fingerprint="fp1",
                ),
                UserExchangeCredential(
                    user_id=2,
                    exchange="UPBIT",
                    access_key_encrypted="enc-c",
                    secret_key_encrypted="enc-d",
                    access_key_masked="****",
                    access_key_fingerprint="fp2",
                ),
                UserRiskGuard(user_id=1, manual_halt=True, emergency_kill_switch=False, reason="manual-halt"),
            ]
        )
        session.commit()

    scheduler = MultiUserTradingScheduler(session_factory=Session)
    assert scheduler._list_active_user_ids() == [2]


def test_run_user_tick_halt_isolated_to_target_user(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "PAPER")
    Session = _session_factory()
    with Session() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="hash"),
                User(id=2, email="u2@example.com", password_hash="hash"),
            ]
        )
        session.flush()
        session.add(UserRiskGuard(user_id=1, manual_halt=True, emergency_kill_switch=False, reason="operator-halt"))
        session.commit()

    class _DummyUpbit:
        def close(self) -> None:
            return None

    executed_user_ids: list[int] = []

    class _WorkerStub:
        def __init__(self, session, *, user_id: int, access_key=None, secret_key=None, notifier=None):
            self.user_id = user_id
            self.upbit = _DummyUpbit()

        def _run_once(self, cfg: RuntimeConfig) -> None:
            executed_user_ids.append(self.user_id)

    monkeypatch.setattr(scheduler_module, "TradingScheduler", _WorkerStub)

    scheduler = MultiUserTradingScheduler(session_factory=Session)
    now = datetime(2026, 3, 8, 0, 0, tzinfo=timezone.utc)
    cfg = _cfg()
    scheduler._run_user_tick(1, cfg, now)
    scheduler._run_user_tick(2, cfg, now)

    with Session() as session:
        row1 = session.execute(select(UserBotRuntime).where(UserBotRuntime.user_id == 1)).scalar_one()
        row2 = session.execute(select(UserBotRuntime).where(UserBotRuntime.user_id == 2)).scalar_one()

    assert executed_user_ids == [2]
    assert row1.status == "HALTED"
    assert "risk_guard:manual_halt" in (row1.last_error or "")
    assert row2.status == "IDLE"
    assert row2.consecutive_failures == 0


def test_daily_loss_limit_halt_isolated_to_impacted_user(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "trade_mode", "PAPER")
    Session = _session_factory()
    with Session() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="hash"),
                User(id=2, email="u2@example.com", password_hash="hash"),
            ]
        )
        session.commit()

    class _DummyUpbit:
        def close(self) -> None:
            return None

    executed_user_ids: list[int] = []
    halted_user_ids: list[int] = []

    class _WorkerStub:
        def __init__(self, session, *, user_id: int, access_key=None, secret_key=None, notifier=None):
            self.user_id = user_id
            self.notifier = notifier
            self.upbit = _DummyUpbit()

        def _run_once(self, cfg: RuntimeConfig) -> None:
            if self.user_id == 1:
                halted_user_ids.append(self.user_id)
                if self.notifier is not None:
                    self.notifier.send("HALT KRW-BTC: daily_loss_limit")
                return
            executed_user_ids.append(self.user_id)

    monkeypatch.setattr(scheduler_module, "TradingScheduler", _WorkerStub)

    scheduler = MultiUserTradingScheduler(session_factory=Session)
    now = datetime(2026, 3, 8, 0, 0, tzinfo=timezone.utc)
    cfg = _cfg()
    scheduler._run_user_tick(1, cfg, now)
    scheduler._run_user_tick(2, cfg, now)

    with Session() as session:
        row1 = session.execute(select(UserBotRuntime).where(UserBotRuntime.user_id == 1)).scalar_one()
        row2 = session.execute(select(UserBotRuntime).where(UserBotRuntime.user_id == 2)).scalar_one()

    assert halted_user_ids == [1]
    assert executed_user_ids == [2]
    assert row1.status == "IDLE"
    assert row1.consecutive_failures == 0
    assert row1.last_error is None
    assert row2.status == "IDLE"
    assert row2.consecutive_failures == 0
    assert row2.last_error is None
