from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base
from trader.data.models import Order, OrderAttempt
from trader.trading.portfolio import PortfolioService
from trader.trading.reconcile import ReconcileService


class FakeReconcileUpbitClient:
    def get_accounts(self):
        return [{"currency": "KRW", "balance": "1000000", "locked": "0"}]

    def get_open_orders(self):
        return [
            {
                "uuid": "upbit-open-uuid-1",
                "identifier": "upbit-open-identifier-1",
                "market": "KRW-BTC",
                "side": "bid",
                "ord_type": "limit",
                "price": "10000",
                "volume": "1",
                "state": "wait",
                "created_at": "2026-03-04T00:00:00+00:00",
            }
        ]


class DummyExecution:
    def sync_local_open_orders(self, user_id: int | None = None):
        return []


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_reconcile_open_orders_creates_order_and_attempt_for_unknown_exchange_order():
    session = _session()
    service = ReconcileService(
        session=session,
        upbit_client=FakeReconcileUpbitClient(),
        portfolio=PortfolioService(session),
        execution=DummyExecution(),
    )

    service._reconcile_open_orders()

    order = session.scalar(select(Order).where(Order.client_order_id == "u1-upbit-upbit-open-uuid-1"))
    assert order is not None
    attempt = session.scalar(select(OrderAttempt).where(OrderAttempt.order_id == order.id))
    assert attempt is not None
    assert attempt.attempt_no == 1
    assert attempt.submit_reason == "RECOVER"
    assert attempt.upbit_identifier == "upbit-open-identifier-1"
    assert attempt.upbit_uuid == "upbit-open-uuid-1"


def test_reconcile_open_orders_uses_next_attempt_no_for_existing_order():
    session = _session()
    order = Order(
        market="KRW-BTC",
        side="bid",
        ord_type="limit",
        requested_price=Decimal("10000"),
        requested_volume=Decimal("1"),
        client_order_id="u1-upbit-upbit-open-uuid-1",
        state="WAIT",
    )
    session.add(order)
    session.flush()
    session.add(
        OrderAttempt(
            order_id=order.id,
            attempt_no=1,
            submit_reason="INITIAL",
            upbit_identifier="old-identifier",
            upbit_uuid="old-uuid",
            state="CANCELED",
        )
    )
    session.commit()

    service = ReconcileService(
        session=session,
        upbit_client=FakeReconcileUpbitClient(),
        portfolio=PortfolioService(session),
        execution=DummyExecution(),
    )

    service._reconcile_open_orders()

    attempts = session.scalars(
        select(OrderAttempt).where(OrderAttempt.order_id == order.id).order_by(OrderAttempt.attempt_no.asc())
    ).all()
    assert len(attempts) == 2
    assert attempts[1].attempt_no == 2
    assert attempts[1].submit_reason == "RECOVER"
