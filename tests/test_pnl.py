from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base
from trader.data.models import DailyEquity, Position
from trader.trading.pnl import PnLService
from trader.trading.portfolio import PortfolioService


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_update_unrealized_pnl_updates_positions():
    session = _session()
    session.add(Position(market="KRW-BTC", qty=Decimal("2"), avg_price=Decimal("100")))
    session.add(Position(market="KRW-ETH", qty=Decimal("0"), avg_price=Decimal("3000"), unrealized_pnl=Decimal("123")))
    session.commit()

    portfolio = PortfolioService(session)
    total = portfolio.update_unrealized_pnl(mark_prices={"KRW-BTC": Decimal("120")})

    assert total == Decimal("40")
    btc = portfolio.get_position("KRW-BTC")
    eth = portfolio.get_position("KRW-ETH")
    assert btc is not None
    assert eth is not None
    assert Decimal(btc.unrealized_pnl) == Decimal("40")
    assert Decimal(eth.unrealized_pnl) == Decimal("0")


def test_daily_snapshot_keeps_start_equity_within_day():
    session = _session()
    pnl = PnLService(session)

    first = pnl.update_daily_snapshot(
        current_equity=Decimal("10000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        as_of_date_utc=date(2026, 2, 24),
    )
    second = pnl.update_daily_snapshot(
        current_equity=Decimal("9900"),
        realized_pnl=Decimal("-50"),
        unrealized_pnl=Decimal("-50"),
        as_of_date_utc=date(2026, 2, 24),
    )

    assert first.start_equity == Decimal("10000")
    assert first.start_realized_pnl == Decimal("0")
    assert second.start_equity == Decimal("10000")
    assert second.start_realized_pnl == Decimal("0")
    assert second.daily_pnl_abs == Decimal("-100")
    assert second.daily_pnl_pct == Decimal("-0.01")


def test_daily_snapshot_creates_new_baseline_on_new_day():
    session = _session()
    pnl = PnLService(session)

    pnl.update_daily_snapshot(
        current_equity=Decimal("10000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        as_of_date_utc=date(2026, 2, 24),
    )
    next_day = pnl.update_daily_snapshot(
        current_equity=Decimal("9800"),
        realized_pnl=Decimal("-200"),
        unrealized_pnl=Decimal("0"),
        as_of_date_utc=date(2026, 2, 25),
    )

    rows = session.query(DailyEquity).order_by(DailyEquity.date_utc.asc()).all()
    assert len(rows) == 2
    assert next_day.start_equity == Decimal("9800")
    assert next_day.start_realized_pnl == Decimal("-200")
    assert next_day.daily_pnl_abs == Decimal("0")
    assert next_day.daily_pnl_pct == Decimal("0")


def test_resolve_daily_pnl_pct_realized_only_uses_realized_delta():
    session = _session()
    pnl = PnLService(session)
    snap = pnl.update_daily_snapshot(
        current_equity=Decimal("10000"),
        realized_pnl=Decimal("100"),
        unrealized_pnl=Decimal("0"),
        as_of_date_utc=date(2026, 2, 24),
    )

    daily_abs, daily_pct = pnl.resolve_daily_pnl_pct(
        snapshot=snap,
        basis="REALIZED_ONLY",
        current_realized_pnl=Decimal("60"),
    )

    assert daily_abs == Decimal("-40")
    assert daily_pct == Decimal("-0.004")


def test_positions_are_isolated_by_user_for_same_market():
    session = _session()
    session.add(Position(user_id=1, market="KRW-BTC", qty=Decimal("2"), avg_price=Decimal("100")))
    session.add(Position(user_id=2, market="KRW-BTC", qty=Decimal("3"), avg_price=Decimal("200")))
    session.commit()

    portfolio = PortfolioService(session)
    user1_total = portfolio.update_unrealized_pnl(mark_prices={"KRW-BTC": Decimal("120")}, user_id=1)
    user2_total = portfolio.update_unrealized_pnl(mark_prices={"KRW-BTC": Decimal("220")}, user_id=2)

    assert user1_total == Decimal("40")
    assert user2_total == Decimal("60")
    row1 = portfolio.get_position("KRW-BTC", user_id=1)
    row2 = portfolio.get_position("KRW-BTC", user_id=2)
    assert row1 is not None and row2 is not None
    assert Decimal(row1.unrealized_pnl) == Decimal("40")
    assert Decimal(row2.unrealized_pnl) == Decimal("60")


def test_daily_snapshot_isolated_by_user_on_same_date():
    session = _session()
    pnl = PnLService(session)

    user1 = pnl.update_daily_snapshot(
        current_equity=Decimal("10000"),
        realized_pnl=Decimal("10"),
        unrealized_pnl=Decimal("0"),
        user_id=1,
        as_of_date_utc=date(2026, 2, 24),
    )
    user2 = pnl.update_daily_snapshot(
        current_equity=Decimal("20000"),
        realized_pnl=Decimal("20"),
        unrealized_pnl=Decimal("0"),
        user_id=2,
        as_of_date_utc=date(2026, 2, 24),
    )

    rows = session.query(DailyEquity).order_by(DailyEquity.user_id.asc(), DailyEquity.date_utc.asc()).all()
    assert len(rows) == 2
    assert user1.start_equity == Decimal("10000")
    assert user2.start_equity == Decimal("20000")
