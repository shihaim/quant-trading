from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.config.config_repo import ConfigRepo
from trader.data.db import Base
from trader.data.models import BotConfig, TimeframeConfig


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
