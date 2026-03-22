from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base
from trader.data.models import Order, OrderAttempt
from trader.trading.order_attempts import (
    latest_attempt_from_rows,
    load_latest_attempt_for_order,
    next_attempt_no_for_order,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_next_attempt_no_for_order_increments_from_existing_rows():
    session = _session()
    order = Order(
        user_id=1,
        market="KRW-BTC",
        side="bid",
        ord_type="limit",
        client_order_id="o-1",
    )
    session.add(order)
    session.flush()
    assert next_attempt_no_for_order(session, order.id) == 1

    session.add(
        OrderAttempt(
            order_id=order.id,
            attempt_no=1,
            submit_reason="INITIAL",
            state="NEW",
            retry_count=0,
        )
    )
    session.flush()
    assert next_attempt_no_for_order(session, order.id) == 2


def test_load_latest_attempt_for_order_prefers_uuid_then_identifier_then_latest():
    session = _session()
    order = Order(
        user_id=1,
        market="KRW-BTC",
        side="bid",
        ord_type="limit",
        client_order_id="o-2",
    )
    session.add(order)
    session.flush()
    first = OrderAttempt(
        order_id=order.id,
        attempt_no=1,
        submit_reason="INITIAL",
        upbit_identifier="id-1",
        upbit_uuid="uuid-1",
        state="NEW",
        retry_count=0,
    )
    second = OrderAttempt(
        order_id=order.id,
        attempt_no=2,
        submit_reason="REPRICE",
        upbit_identifier="id-2",
        upbit_uuid="uuid-2",
        state="SENT",
        retry_count=1,
    )
    session.add_all([first, second])
    session.flush()

    assert load_latest_attempt_for_order(session, order_id=order.id, upbit_uuid="uuid-2").id == second.id
    assert load_latest_attempt_for_order(session, order_id=order.id, upbit_identifier="id-1").id == first.id
    assert load_latest_attempt_for_order(session, order_id=order.id).id == second.id


def test_latest_attempt_from_rows_picks_highest_attempt_no():
    session = _session()
    order = Order(
        user_id=1,
        market="KRW-ETH",
        side="ask",
        ord_type="limit",
        client_order_id="o-3",
    )
    session.add(order)
    session.flush()
    a = OrderAttempt(order_id=order.id, attempt_no=2, submit_reason="REPRICE", state="OPEN", retry_count=1)
    b = OrderAttempt(order_id=order.id, attempt_no=3, submit_reason="RECOVER", state="OPEN", retry_count=1)
    session.add_all([a, b])
    session.flush()

    latest = latest_attempt_from_rows([a, b])
    assert latest is not None
    assert latest.id == b.id
