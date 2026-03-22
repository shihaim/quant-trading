from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trader.data.models import Order, OrderAttempt, TradeMetric
from trader.trading.order_attempts import latest_attempt_from_rows

KST = timezone(timedelta(hours=9))


def ensure_utc(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def iso_utc(ts: datetime | None) -> str | None:
    normalized = ensure_utc(ts)
    if normalized is None:
        return None
    return normalized.isoformat().replace("+00:00", "Z")


def iso_kst(ts: datetime | None) -> str | None:
    normalized = ensure_utc(ts)
    if normalized is None:
        return None
    return normalized.astimezone(KST).isoformat()


def to_decimal(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def to_float(value: Decimal | float | int | None) -> float:
    return float(to_decimal(value))


def latest_attempt(row: Order) -> OrderAttempt | None:
    return latest_attempt_from_rows(getattr(row, "attempts", None))


def to_order_item(row: Order) -> dict:
    attempt = latest_attempt(row)
    updated_at = attempt.updated_at if attempt is not None else row.updated_at
    state = attempt.state if attempt is not None else row.state
    error_class = attempt.error_class if attempt is not None else row.error_class
    last_error = attempt.last_error if attempt is not None else row.last_error
    upbit_identifier = attempt.upbit_identifier if attempt is not None else row.upbit_identifier
    upbit_uuid = attempt.upbit_uuid if attempt is not None else row.upbit_uuid
    return {
        "id": row.id,
        "updated_at_utc": iso_utc(updated_at),
        "updated_at_kst": iso_kst(updated_at),
        "market": row.market,
        "side": row.side,
        "intent": row.intent,
        "state": state,
        "error_class": error_class,
        "last_error": last_error,
        "client_order_id": row.client_order_id,
        "upbit_identifier": upbit_identifier,
        "upbit_uuid": upbit_uuid,
        "attempt_no": attempt.attempt_no if attempt is not None else None,
        "attempt_submit_reason": attempt.submit_reason if attempt is not None else None,
    }


def to_trade_metric_list_item(metric: TradeMetric, market: str | None, side: str | None) -> dict:
    return {
        "order_id": metric.order_id,
        "created_at_utc": iso_utc(metric.created_at),
        "created_at_kst": iso_kst(metric.created_at),
        "market": market,
        "side": side,
        "intent": metric.intent,
        "intended_price": to_float(metric.intended_price) if metric.intended_price is not None else None,
        "filled_vwap_price": to_float(metric.filled_vwap_price) if metric.filled_vwap_price is not None else None,
        "slippage_abs": to_float(metric.slippage_abs) if metric.slippage_abs is not None else None,
        "slippage_pct": to_float(metric.slippage_pct) if metric.slippage_pct is not None else None,
        "fee_abs": to_float(metric.fee_abs),
        "time_to_fill_ms": metric.time_to_fill_ms,
        "partial_fill_count": metric.partial_fill_count,
    }


def to_trade_metric_summary_item(metric: TradeMetric, market: str | None, side: str | None) -> dict:
    return {
        "order_id": metric.order_id,
        "executed_at_utc": iso_utc(metric.created_at),
        "market": market,
        "side": side,
        "intent": metric.intent,
        "intended_price": to_float(metric.intended_price) if metric.intended_price is not None else None,
        "filled_vwap_price": to_float(metric.filled_vwap_price) if metric.filled_vwap_price is not None else None,
        "slippage_abs": to_float(metric.slippage_abs) if metric.slippage_abs is not None else None,
        "slippage_pct": to_float(metric.slippage_pct) if metric.slippage_pct is not None else None,
        "fee_abs": to_float(metric.fee_abs),
        "time_to_fill_ms": metric.time_to_fill_ms,
        "partial_fill_count": metric.partial_fill_count,
    }
