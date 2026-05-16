from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.config.config_repo import ConfigRepo
from trader.data.db import Base
from trader.data.models import BotConfig, TimeframeConfig, User, UserBotConfig


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


def test_load_for_user_reads_extended_risk_policy_fields():
    session = _session()
    session.add(BotConfig(id=1, timeframe="15m", markets_json='["KRW-BTC"]'))
    session.add(User(email="u2@example.com", password_hash="hash"))
    session.flush()
    session.add(
        UserBotConfig(
            user_id=1,
            timeframe="30m",
            markets_json='["KRW-ETH"]',
            max_weekly_loss_pct=0.03,
            max_monthly_loss_pct=0.08,
            cooldown_hours_on_halt=6,
            max_new_orders_per_day=12,
            max_orders_per_week=50,
            min_edge_pct=0.0025,
        )
    )
    session.commit()

    cfg = ConfigRepo(session).load_for_user(1)

    assert cfg.max_weekly_loss_pct == Decimal("0.03")
    assert cfg.max_monthly_loss_pct == Decimal("0.08")
    assert cfg.cooldown_hours_on_halt == 6
    assert cfg.max_new_orders_per_day == 12
    assert cfg.max_orders_per_week == 50
    assert cfg.min_edge_pct == Decimal("0.0025")


def test_load_for_user_creates_user_config_without_global_bot_config_fallback():
    session = _session()
    session.add(BotConfig(id=1, timeframe="240m", markets_json='["KRW-ETH"]'))
    session.add(User(email="default-user-config@example.com", password_hash="hash"))
    session.commit()

    cfg = ConfigRepo(session).load_for_user(1)

    row = session.query(UserBotConfig).filter_by(user_id=1).one()
    assert cfg.timeframe == "15m"
    assert cfg.markets == ["KRW-BTC"]
    assert row.timeframe == "15m"
    assert row.markets_json == '["KRW-BTC"]'


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


