from __future__ import annotations

from decimal import Decimal

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base
from trader.data.models import Order
from trader.trading.execution import ExecutionEngine
from trader.trading.paper_execution import PaperExecutionEngine
from trader.trading.portfolio import PortfolioService


class FakeUpbitClient:
    def __init__(self):
        self.created: dict[str, dict] = {}
        self.create_calls = 0
        self.test_calls = 0
        self.fail_create_once = False
        self.get_order_state = "done"

    def get_order_chance(self, market, cache_ttl_seconds=900):
        return {
            "market": {
                "bid": {"min_total": "5000"},
                "ask": {"min_total": "5000"},
            }
        }

    def test_order(self, market, side, ord_type, volume=None, price=None, identifier=None):
        self.test_calls += 1
        return {"result": "ok", "identifier": identifier}

    def create_order(self, market, side, ord_type, volume=None, price=None, identifier=None):
        self.create_calls += 1
        if self.fail_create_once:
            self.fail_create_once = False
            req = httpx.Request("POST", "https://api.upbit.com/v1/orders")
            raise httpx.TimeoutException("timeout", request=req)
        payload = {"uuid": f"uuid-{identifier}", "state": "wait"}
        self.created[identifier] = payload
        return payload

    def get_order(self, order_uuid):
        identifier = order_uuid.replace("uuid-", "")
        if self.get_order_state == "wait":
            return {
                "uuid": order_uuid,
                "state": "wait",
                "executed_volume": "0",
                "trades": [],
            }
        return {
            "uuid": order_uuid,
            "state": "done",
            "executed_volume": "1",
            "trades": [
                {
                    "trade_uuid": f"trade-{identifier}",
                    "price": "10000",
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


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_execution_idempotency_key_creates_single_order():
    session = _session()
    client = FakeUpbitClient()
    engine = ExecutionEngine(session=session, upbit_client=client, max_submit_retries=2, trade_mode="REAL")
    first = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="15m-KRW-BTC-2026-02-24T10:00:00+00:00",
    )
    second = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="15m-KRW-BTC-2026-02-24T10:00:00+00:00",
    )
    assert first is not None
    assert second is not None
    orders = session.scalars(select(Order)).all()
    assert len(orders) == 1


def test_validation_rejects_below_min_total_without_submit():
    session = _session()
    client = FakeUpbitClient()
    engine = ExecutionEngine(session=session, upbit_client=client, max_submit_retries=2, trade_mode="REAL")
    order = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("0.1"),
        ref_price=Decimal("1000"),
        idempotency_key="15m-KRW-BTC-2026-02-24T10:15:00+00:00",
    )
    assert order is not None
    assert order.state == "REJECTED"
    assert order.error_class == "VALIDATION_ERROR"
    assert client.create_calls == 0


def test_test_mode_calls_orders_test_only():
    session = _session()
    client = FakeUpbitClient()
    engine = ExecutionEngine(session=session, upbit_client=client, max_submit_retries=2, trade_mode="TEST")
    order = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="15m-KRW-BTC-2026-02-24T10:30:00+00:00",
    )
    assert order is not None
    assert order.state == "TEST_OK"
    assert client.test_calls == 1
    assert client.create_calls == 0


def test_allowlist_rejects_market_without_submit():
    session = _session()
    client = FakeUpbitClient()
    engine = ExecutionEngine(
        session=session,
        upbit_client=client,
        max_submit_retries=2,
        trade_mode="REAL",
        allowed_markets={"KRW-BTC"},
    )
    order = engine.place_target_order(
        market="KRW-ETH",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="15m-KRW-ETH-2026-02-24T11:00:00+00:00",
    )
    assert order is not None
    assert order.state == "REJECTED"
    assert order.error_class == "VALIDATION_ERROR"
    assert client.create_calls == 0
    assert client.test_calls == 0


def test_cancel_order_transitions_to_canceled():
    session = _session()
    client = FakeUpbitClient()
    client.get_order_state = "wait"
    engine = ExecutionEngine(
        session=session,
        upbit_client=client,
        max_submit_retries=2,
        trade_mode="REAL",
    )
    order = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="15m-KRW-BTC-2026-02-24T11:15:00+00:00",
    )
    assert order is not None
    assert order.state in {"OPEN", "WAIT"}
    canceled = engine.cancel_order(order)
    assert canceled.state == "CANCELED"


def test_paper_execution_updates_wallet_and_position_once():
    session = _session()
    portfolio = PortfolioService(session)
    paper = PaperExecutionEngine(session=session, fee_rate=Decimal("0.0005"))
    order = paper.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="15m-KRW-BTC-2026-02-24T10:00:00+00:00",
    )
    assert order is not None
    applied = portfolio.apply_unapplied_fills(order, use_paper_wallet=True, initial_cash_krw=Decimal("100000"))
    assert applied == 1
    position = portfolio.get_position("KRW-BTC")
    wallet = portfolio.get_or_create_paper_wallet(Decimal("100000"))
    assert position is not None
    assert Decimal(position.qty) == Decimal("1")
    assert Decimal(wallet.cash_krw) == Decimal("89995")
