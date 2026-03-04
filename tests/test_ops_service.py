from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base
from trader.data.models import BotConfig, DailyEquity, Order, OrderAttempt, TradeMetric
from trader.ops.service import OpsService


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def _add_order(
    session,
    *,
    market: str = "KRW-BTC",
    side: str = "bid",
    state: str = "OPEN",
    intent: str | None = "ENTRY",
    client_order_id: str,
    error_class: str | None = None,
    last_error: str | None = None,
):
    row = Order(
        market=market,
        side=side,
        ord_type="limit",
        requested_price=Decimal("100"),
        requested_volume=Decimal("1"),
        client_order_id=client_order_id,
        intent=intent,
        state=state,
        error_class=error_class,
        last_error=last_error,
        upbit_identifier=f"id-{client_order_id}",
        upbit_uuid=f"uuid-{client_order_id}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    return row


def _add_attempt(
    session,
    order: Order,
    *,
    attempt_no: int,
    submit_reason: str = "INITIAL",
    state: str = "OPEN",
    upbit_identifier: str | None = None,
    upbit_uuid: str | None = None,
    error_class: str | None = None,
    last_error: str | None = None,
):
    row = OrderAttempt(
        order_id=order.id,
        attempt_no=attempt_no,
        submit_reason=submit_reason,
        requested_price=order.requested_price,
        requested_volume=order.requested_volume,
        state=state,
        upbit_identifier=upbit_identifier,
        upbit_uuid=upbit_uuid,
        error_class=error_class,
        last_error=last_error,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    return row


def test_ops_summary_aggregates_counts_pnl_and_metrics():
    session = _session()
    today = datetime.now(timezone.utc).date()

    session.add(
        BotConfig(
            id=1,
            is_enabled=True,
            timeframe="240m",
            markets_json='["KRW-BTC"]',
            target_exposure_pct=Decimal("0.30"),
            daily_loss_basis="REALIZED_ONLY",
            max_daily_loss_pct=Decimal("0.005"),
            max_total_exposure_pct=Decimal("0.50"),
            max_per_market_exposure_pct=Decimal("0.50"),
            slippage_budget_entry_pct=Decimal("0.0005"),
            slippage_budget_exit_pct=Decimal("0.0020"),
            slippage_budget_breach_halt_count=3,
            updated_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        DailyEquity(
            date_utc=today,
            start_equity=Decimal("1000000"),
            start_realized_pnl=Decimal("0"),
            last_equity=Decimal("996880"),
            realized_pnl=Decimal("-1200"),
            unrealized_pnl=Decimal("-1920"),
            daily_pnl_abs=Decimal("-3120"),
            daily_pnl_pct=Decimal("-0.00312"),
            updated_at=datetime.now(timezone.utc),
        )
    )

    _add_order(session, state="OPEN", client_order_id="order-open-1")
    _add_order(session, state="PARTIAL", client_order_id="order-partial-1")
    _add_order(session, state="NEW", client_order_id="order-new-1")
    _add_order(session, state="WAIT", client_order_id="order-wait-1")
    _add_order(
        session,
        state="ERROR_NEEDS_REVIEW",
        client_order_id="order-review-1",
        error_class="UpbitApiError",
        last_error="401 Unauthorized",
    )
    metric_order_1 = _add_order(session, side="ask", intent="EXIT", state="FILLED", client_order_id="order-metric-1")
    metric_order_2 = _add_order(session, side="bid", intent="ENTRY", state="FILLED", client_order_id="order-metric-2")
    metric_order_3 = _add_order(session, side="bid", intent="ENTRY", state="FILLED", client_order_id="order-metric-3")

    session.add_all(
        [
            TradeMetric(
                order_id=metric_order_1.id,
                intent="EXIT",
                intended_price=Decimal("100"),
                filled_vwap_price=Decimal("99.7"),
                slippage_abs=Decimal("0.3"),
                slippage_pct=Decimal("0.003"),
                fee_abs=Decimal("0.01"),
                time_to_fill_ms=1200,
                partial_fill_count=0,
                created_at=datetime.now(timezone.utc),
            ),
            TradeMetric(
                order_id=metric_order_2.id,
                intent="ENTRY",
                intended_price=Decimal("100"),
                filled_vwap_price=Decimal("100.04"),
                slippage_abs=Decimal("0.04"),
                slippage_pct=Decimal("0.0004"),
                fee_abs=Decimal("0.01"),
                time_to_fill_ms=800,
                partial_fill_count=1,
                created_at=datetime.now(timezone.utc),
            ),
            TradeMetric(
                order_id=metric_order_3.id,
                intent="ENTRY",
                intended_price=Decimal("100"),
                filled_vwap_price=Decimal("100.07"),
                slippage_abs=Decimal("0.07"),
                slippage_pct=Decimal("0.0007"),
                fee_abs=Decimal("0.01"),
                time_to_fill_ms=1000,
                partial_fill_count=2,
                created_at=datetime.now(timezone.utc),
            ),
        ]
    )
    session.commit()

    summary = OpsService(session=session, trade_mode="REAL").get_summary(metrics_limit=200, needs_review_limit=10)

    assert summary["trade_mode"] == "REAL"
    assert summary["bot"]["status"] == "RUNNING"
    assert summary["orders"]["counts"]["OPEN"] == 1
    assert summary["orders"]["counts"]["PARTIAL"] == 1
    assert summary["orders"]["counts"]["IN_FLIGHT"] == 2
    assert summary["orders"]["counts"]["ERROR_NEEDS_REVIEW"] == 1
    assert len(summary["orders"]["needs_review_top"]) == 1
    assert summary["today_pnl"]["basis_used"] == "REALIZED_ONLY"
    assert summary["today_pnl"]["daily_pnl_pct"] == pytest.approx(-0.0012, rel=1e-9)
    assert summary["execution_quality"]["budget"]["breach_count_24h"] == 2
    assert summary["execution_quality"]["kpi"]["p95_slippage_pct"] == pytest.approx(0.003, rel=1e-9)


def test_ops_summary_marks_halted_when_disabled_and_loss_limit_breached():
    session = _session()
    today = datetime.now(timezone.utc).date()

    session.add(
        BotConfig(
            id=1,
            is_enabled=False,
            timeframe="240m",
            markets_json='["KRW-BTC"]',
            daily_loss_basis="TOTAL",
            max_daily_loss_pct=Decimal("0.005"),
            updated_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        DailyEquity(
            date_utc=today,
            start_equity=Decimal("1000000"),
            start_realized_pnl=Decimal("0"),
            last_equity=Decimal("994000"),
            realized_pnl=Decimal("-2000"),
            unrealized_pnl=Decimal("0"),
            daily_pnl_abs=Decimal("-6000"),
            daily_pnl_pct=Decimal("-0.006"),
            updated_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    summary = OpsService(session=session, trade_mode="PAPER").get_summary()

    assert summary["bot"]["status"] == "HALTED"
    assert summary["halt"]["is_halted"] is True
    assert summary["halt"]["reason"] == "daily_loss_limit"


def test_list_orders_prefers_latest_attempt_fields():
    session = _session()
    order = _add_order(
        session,
        state="WAIT",
        client_order_id="order-attempt-view-1",
        error_class=None,
        last_error=None,
    )
    _add_attempt(
        session,
        order,
        attempt_no=1,
        submit_reason="INITIAL",
        state="WAIT",
        upbit_identifier="attempt-1",
        upbit_uuid="uuid-attempt-1",
    )
    _add_attempt(
        session,
        order,
        attempt_no=2,
        submit_reason="REPRICE",
        state="ERROR_NEEDS_REVIEW",
        upbit_identifier="attempt-2",
        upbit_uuid="uuid-attempt-2",
        error_class="NETWORK_TIMEOUT",
        last_error="timed out",
    )
    session.commit()

    payload = OpsService(session=session, trade_mode="REAL").list_orders(limit=10)

    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["client_order_id"] == "order-attempt-view-1"
    assert item["state"] == "ERROR_NEEDS_REVIEW"
    assert item["error_class"] == "NETWORK_TIMEOUT"
    assert item["last_error"] == "timed out"
    assert item["upbit_identifier"] == "attempt-2"
    assert item["upbit_uuid"] == "uuid-attempt-2"
    assert item["attempt_no"] == 2
    assert item["attempt_submit_reason"] == "REPRICE"
