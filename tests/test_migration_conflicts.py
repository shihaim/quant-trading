from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base
from trader.data.models import Fill, Order, TradeMetric
from trader.migration.contracts import MigrationOptions
from trader.migration.merge import MigrationService


def _sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path.resolve().as_posix()}"


def _session_factory(path: Path):
    url = _sqlite_url(path)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return url, engine, Session


def test_orders_conflict_warns_and_skips_when_identity_mismatch(tmp_path):
    source_url, source_engine, SourceSession = _session_factory(tmp_path / "source-orders.db")
    target_url, target_engine, TargetSession = _session_factory(tmp_path / "target-orders.db")

    with SourceSession() as session:
        session.add(
            Order(
                market="KRW-BTC",
                side="bid",
                ord_type="limit",
                requested_price=10000,
                requested_volume=1,
                client_order_id="shared-order",
                state="OPEN",
            )
        )
        session.commit()

    with TargetSession() as session:
        session.add(
            Order(
                market="KRW-ETH",
                side="bid",
                ord_type="limit",
                requested_price=10000,
                requested_volume=1,
                client_order_id="shared-order",
                state="OPEN",
            )
        )
        session.commit()

    summary = MigrationService().run(
        MigrationOptions(
            source_url=source_url,
            target_url=target_url,
            tables=("orders",),
            bootstrap_target=False,
        )
    )

    stats = summary.table_stats[0]
    assert stats.inserted == 0
    assert stats.updated == 0
    assert stats.skipped == 1
    assert any("Order conflict" in warning for warning in stats.warnings)

    with TargetSession() as session:
        row = session.scalar(select(Order).where(Order.client_order_id == "shared-order"))
        assert row is not None
        assert row.market == "KRW-ETH"

    source_engine.dispose()
    target_engine.dispose()


def test_fill_conflict_raises_in_strict_mode(tmp_path):
    source_url, source_engine, SourceSession = _session_factory(tmp_path / "source-fills.db")
    target_url, target_engine, TargetSession = _session_factory(tmp_path / "target-fills.db")

    with SourceSession() as session:
        source_order = Order(
            market="KRW-BTC",
            side="bid",
            ord_type="limit",
            requested_price=10000,
            requested_volume=1,
            client_order_id="shared-order",
            state="FILLED",
        )
        session.add(source_order)
        session.flush()
        session.add(
            Fill(
                order_id=source_order.id,
                trade_id="shared-trade",
                price=10000,
                volume=1,
                fee=5,
            )
        )
        session.commit()

    with TargetSession() as session:
        target_order = Order(
            market="KRW-BTC",
            side="bid",
            ord_type="limit",
            requested_price=10000,
            requested_volume=1,
            client_order_id="shared-order",
            state="FILLED",
        )
        session.add(target_order)
        session.flush()
        session.add(
            Fill(
                order_id=target_order.id,
                trade_id="shared-trade",
                price=9999,
                volume=1,
                fee=5,
            )
        )
        session.commit()

    with pytest.raises(ValueError, match="Fill conflict"):
        MigrationService().run(
            MigrationOptions(
                source_url=source_url,
                target_url=target_url,
                tables=("fills",),
                bootstrap_target=False,
                strict=True,
            )
        )

    source_engine.dispose()
    target_engine.dispose()


def test_trade_metric_conflict_warns_when_target_is_newer(tmp_path):
    source_url, source_engine, SourceSession = _session_factory(tmp_path / "source-metrics.db")
    target_url, target_engine, TargetSession = _session_factory(tmp_path / "target-metrics.db")
    source_created_at = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    target_created_at = source_created_at + timedelta(minutes=5)

    with SourceSession() as session:
        source_order = Order(
            market="KRW-BTC",
            side="bid",
            ord_type="limit",
            requested_price=10000,
            requested_volume=1,
            client_order_id="shared-order",
            state="FILLED",
        )
        session.add(source_order)
        session.flush()
        session.add(
            TradeMetric(
                order_id=source_order.id,
                intent="ENTRY",
                intended_price=10000,
                filled_vwap_price=10010,
                slippage_abs=10,
                slippage_pct=0.001,
                fee_abs=5,
                time_to_fill_ms=1000,
                partial_fill_count=1,
                created_at=source_created_at,
            )
        )
        session.commit()

    with TargetSession() as session:
        target_order = Order(
            market="KRW-BTC",
            side="bid",
            ord_type="limit",
            requested_price=10000,
            requested_volume=1,
            client_order_id="shared-order",
            state="FILLED",
        )
        session.add(target_order)
        session.flush()
        session.add(
            TradeMetric(
                order_id=target_order.id,
                intent="ENTRY",
                intended_price=10000,
                filled_vwap_price=10020,
                slippage_abs=20,
                slippage_pct=0.002,
                fee_abs=5,
                time_to_fill_ms=1100,
                partial_fill_count=1,
                created_at=target_created_at,
            )
        )
        session.commit()

    summary = MigrationService().run(
        MigrationOptions(
            source_url=source_url,
            target_url=target_url,
            tables=("trade_metrics",),
            bootstrap_target=False,
        )
    )

    stats = summary.table_stats[0]
    assert stats.inserted == 0
    assert stats.updated == 0
    assert stats.skipped == 1
    assert any("TradeMetric conflict" in warning for warning in stats.warnings)

    with TargetSession() as session:
        metric = session.scalar(select(TradeMetric))
        assert metric is not None
        assert metric.created_at.replace(tzinfo=timezone.utc) == target_created_at
        assert metric.filled_vwap_price == 10020

    source_engine.dispose()
    target_engine.dispose()
