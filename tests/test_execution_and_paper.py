from __future__ import annotations

from decimal import Decimal

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import trader.trading.execution as execution_module
from trader.data.db import Base
from trader.data.models import Order
from trader.trading.execution import ExecutionEngine
from trader.trading.order_policy import OrderPolicyConfig
from trader.trading.paper_execution import PaperExecutionEngine
from trader.trading.portfolio import PortfolioService


class FakeUpbitClient:
    def __init__(self):
        self.created: dict[str, dict] = {}
        self.create_calls = 0
        self.submitted_identifiers: list[str | None] = []
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
        self.submitted_identifiers.append(identifier)
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


def test_conflicting_open_order_is_canceled_before_new_side_order():
    session = _session()
    client = FakeUpbitClient()
    client.get_order_state = "wait"
    engine = ExecutionEngine(session=session, upbit_client=client, max_submit_retries=2, trade_mode="REAL")

    first = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="conflict-1",
    )
    assert first is not None
    assert first.state in {"OPEN", "WAIT"}

    second = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("1"),
        target_qty=Decimal("0"),
        ref_price=Decimal("10000"),
        idempotency_key="conflict-2",
    )
    assert second is not None
    refreshed_first = session.get(Order, first.id)
    assert refreshed_first is not None
    assert refreshed_first.state == "CANCELED"


def test_reprice_uses_new_upbit_identifier(monkeypatch):
    session = _session()
    client = FakeUpbitClient()
    client.get_order_state = "wait"
    engine = ExecutionEngine(
        session=session,
        upbit_client=client,
        max_submit_retries=2,
        retry_backoff_seconds=0,
        trade_mode="REAL",
    )
    monotonic_values = iter([0.0, 2.0, 10.0, 12.0])
    monkeypatch.setattr(execution_module.time, "monotonic", lambda: next(monotonic_values))

    order = engine.place_target_order(
        market="KRW-BTC",
        current_qty=Decimal("0"),
        target_qty=Decimal("1"),
        ref_price=Decimal("10000"),
        idempotency_key="reprice-identifier",
        policy_config=OrderPolicyConfig(
            fill_timeout_sec_entry=1,
            fill_timeout_sec_exit=4,
            fill_timeout_sec_rebalance=10,
            max_reprice_attempts_entry=2,
            max_reprice_attempts_exit=1,
            max_reprice_attempts_rebalance=1,
            reprice_step_bps=10,
            allow_market_fallback_on_exit=False,
        ),
    )

    assert order is not None
    assert client.create_calls == 2
    assert len(client.submitted_identifiers) == 2
    assert client.submitted_identifiers[0] != client.submitted_identifiers[1]


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
