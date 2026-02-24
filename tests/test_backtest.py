from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.backtest.engine import BacktestConfig, BacktestEngine
from trader.data.db import Base
from trader.data.models import Candle


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_backtest_runs_with_local_candles():
    session = _session()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(160):
        px = Decimal("100000") + (Decimal("1000") * i)
        session.add(
            Candle(
                market="KRW-BTC",
                timeframe="15m",
                candle_time_utc=start + timedelta(minutes=15 * i),
                open=px,
                high=px + Decimal("100"),
                low=px - Decimal("100"),
                close=px,
                volume=Decimal("10"),
            )
        )
    session.commit()
    engine = BacktestEngine(session)
    result = engine.run(
        BacktestConfig(
            market="KRW-BTC",
            timeframe="15m",
            initial_cash_krw=Decimal("1000000"),
            fee_rate=Decimal("0.0005"),
            slippage_bps=Decimal("5"),
        )
    )
    assert result.trades >= 1
    assert result.end_equity > Decimal("0")

