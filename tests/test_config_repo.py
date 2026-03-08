from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.config.config_repo import ConfigRepo
from trader.data.db import Base
from trader.data.models import BotConfig, TimeframeConfig, User, UserBotConfig, UserExchangeCredential


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_load_reads_enabled_timeframe_from_timeframe_config():
    session = _session()
    session.add(BotConfig(id=1, timeframe="15m", markets_json='["KRW-BTC"]'))
    session.add(TimeframeConfig(timeframe="5m", is_enabled=True))
    session.commit()

    cfg = ConfigRepo(session).load()

    assert cfg.timeframe == "5m"
    assert cfg.is_enabled is True


def test_load_uses_limit_one_when_multiple_enabled_rows():
    session = _session()
    session.add(BotConfig(id=1, timeframe="15m", markets_json='["KRW-BTC"]'))
    session.add(TimeframeConfig(timeframe="3m", is_enabled=True))
    session.add(TimeframeConfig(timeframe="5m", is_enabled=True))
    session.commit()

    cfg = ConfigRepo(session).load()

    # Query uses ORDER BY id ASC LIMIT 1.
    assert cfg.timeframe == "3m"


def test_load_falls_back_to_bot_config_timeframe_when_none_enabled():
    session = _session()
    session.add(BotConfig(id=1, timeframe="15m", markets_json='["KRW-BTC"]'))
    session.add(TimeframeConfig(timeframe="5m", is_enabled=False))
    session.commit()

    cfg = ConfigRepo(session).load()

    assert cfg.timeframe == "15m"


def test_load_reads_target_exposure_pct_from_bot_config():
    session = _session()
    session.add(BotConfig(id=1, timeframe="15m", markets_json='["KRW-BTC"]', target_exposure_pct=0.15))
    session.add(TimeframeConfig(timeframe="15m", is_enabled=True))
    session.commit()

    cfg = ConfigRepo(session).load()

    assert cfg.target_exposure_pct == Decimal("0.15")


def test_load_reads_daily_loss_basis_from_bot_config():
    session = _session()
    session.add(BotConfig(id=1, timeframe="15m", markets_json='["KRW-BTC"]', daily_loss_basis="REALIZED_ONLY"))
    session.add(TimeframeConfig(timeframe="15m", is_enabled=True))
    session.commit()

    cfg = ConfigRepo(session).load()

    assert cfg.daily_loss_basis == "REALIZED_ONLY"


def test_load_falls_back_to_total_when_daily_loss_basis_invalid():
    session = _session()
    session.add(BotConfig(id=1, timeframe="15m", markets_json='["KRW-BTC"]', daily_loss_basis="UNKNOWN"))
    session.add(TimeframeConfig(timeframe="15m", is_enabled=True))
    session.commit()

    cfg = ConfigRepo(session).load()

    assert cfg.daily_loss_basis == "TOTAL"


def test_load_for_user_prefers_user_bot_config():
    session = _session()
    session.add(BotConfig(id=1, timeframe="15m", markets_json='["KRW-BTC"]'))
    session.add(User(email="u1@example.com", password_hash="hash"))
    session.flush()
    session.add(
        UserBotConfig(
            user_id=1,
            timeframe="30m",
            markets_json='["KRW-ETH"]',
            daily_loss_basis="REALIZED_ONLY",
            max_daily_loss_pct=0.05,
            max_total_exposure_pct=0.40,
            max_per_market_exposure_pct=0.20,
        )
    )
    session.commit()

    cfg = ConfigRepo(session).load_for_user(1)

    assert cfg.timeframe == "30m"
    assert cfg.markets == ["KRW-ETH"]
    assert cfg.daily_loss_basis == "REALIZED_ONLY"


def test_runtime_state_defaults_and_set_enabled():
    session = _session()
    session.add(User(email="runtime@example.com", password_hash="hash"))
    session.commit()

    repo = ConfigRepo(session)
    state = repo.get_runtime_state(1)
    assert state.user_id == 1
    assert state.is_enabled is True
    assert state.status == "IDLE"

    updated = repo.set_runtime_enabled(user_id=1, enabled=False)
    assert updated.user_id == 1
    assert updated.is_enabled is False


def test_get_risk_guard_defaults_to_not_halted():
    session = _session()
    session.add(User(email="risk@example.com", password_hash="hash"))
    session.commit()

    state = ConfigRepo(session).get_risk_guard(1)

    assert state.user_id == 1
    assert state.manual_halt is False
    assert state.emergency_kill_switch is False
    assert state.is_halted is False


def test_resolve_owner_user_id_prefers_upbit_credential_owner():
    session = _session()
    session.add_all(
        [
            User(email="a@example.com", password_hash="hash"),
            User(email="b@example.com", password_hash="hash"),
        ]
    )
    session.flush()
    session.add(UserExchangeCredential(user_id=2, exchange="UPBIT", access_key_encrypted="a", secret_key_encrypted="b", access_key_masked="****", access_key_fingerprint="fp"))
    session.commit()

    owner_id = ConfigRepo(session).resolve_owner_user_id()
    assert owner_id == 2
