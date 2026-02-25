from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base
from trader.trading.execution import ExecutionEngine


class FakeUpbitClient:
    def __init__(self, trade_price: str = "10010"):
        self.trade_price = trade_price
        self.created: dict[str, dict] = {}

    def get_order_chance(self, market, cache_ttl_seconds=900):
        return {
            "market": {
                "bid": {"min_total": "5000"},
                "ask": {"min_total": "5000"},
            }
        }

    def create_order(self, market, side, ord_type, volume=None, price=None, identifier=None):
        payload = {"uuid": f"uuid-{identifier}", "state": "wait"}
        self.created[identifier] = payload
        return payload

    def get_order(self, order_uuid):
        return {
            "uuid": order_uuid,
            "state": "done",
            "executed_volume": "1",
            "trades": [
                {
                    "trade_uuid": f"trade-{order_uuid}",
                    "price": self.trade_price,
                    "volume": "1",
                    "fee": "5",
                }
            ],
        }

    def get_order_by_identifier(self, identifier):
        payload = self.created.get(identifier)
        if not payload:
            return None
        return {
            "uuid": payload["uuid"],
            "state": payload["state"],
            "executed_volume": "0",
            "trades": [],
        }

    def cancel_order(self, order_uuid):
        return {"uuid": order_uuid, "state": "cancel", "trades": []}

    def test_order(self, *args, **kwargs):
        return {"result": "ok"}


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_trade_metric_records_buy_slippage_as_positive_when_worse_fill():
    session = _session()
    client = FakeUpbitClient(trade_price="10010")
    engine = ExecutionEngine(session=session, upbit_client=client, trade_mode="REAL")

    order = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="metric-buy-1",
    )
    assert order is not None

    metric = engine.latest_trade_metric(order.id)
    assert metric is not None
    assert Decimal(metric.filled_vwap_price) == Decimal("10010")
    assert Decimal(metric.slippage_abs) == Decimal("10")
    assert Decimal(metric.slippage_pct) == Decimal("0.001")
    assert metric.partial_fill_count == 1
    assert metric.time_to_fill_ms >= 0


def test_trade_metric_records_sell_slippage_as_positive_when_worse_fill():
    session = _session()
    client = FakeUpbitClient(trade_price="9990")
    engine = ExecutionEngine(session=session, upbit_client=client, trade_mode="REAL")

    order = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("1"),
        target_qty=Decimal("0"),
        ref_price=Decimal("10000"),
        idempotency_key="metric-sell-1",
    )
    assert order is not None

    metric = engine.latest_trade_metric(order.id)
    assert metric is not None
    assert Decimal(metric.filled_vwap_price) == Decimal("9990")
    assert Decimal(metric.slippage_abs) == Decimal("10")
    assert Decimal(metric.slippage_pct) == Decimal("0.001")
