from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from trader.data.db import Base


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class BotConfig(Base):
    """Runtime trading configuration."""

    __tablename__ = "bot_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    timeframe: Mapped[str] = mapped_column(String(16), default="15m")
    markets_json: Mapped[str] = mapped_column(Text, default='["KRW-BTC"]')
    target_exposure_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.10"))
    daily_loss_basis: Mapped[str] = mapped_column(String(32), default="TOTAL")
    min_rebalance_threshold_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.05"))
    min_order_krw_buffer: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    fill_timeout_sec_entry: Mapped[int] = mapped_column(Integer, default=10)
    fill_timeout_sec_exit: Mapped[int] = mapped_column(Integer, default=4)
    fill_timeout_sec_rebalance: Mapped[int] = mapped_column(Integer, default=10)
    max_reprice_attempts_entry: Mapped[int] = mapped_column(Integer, default=2)
    max_reprice_attempts_exit: Mapped[int] = mapped_column(Integer, default=1)
    max_reprice_attempts_rebalance: Mapped[int] = mapped_column(Integer, default=1)
    reprice_step_bps: Mapped[int] = mapped_column(Integer, default=10)
    slippage_budget_entry_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.0005"))
    slippage_budget_exit_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.0020"))
    slippage_budget_breach_halt_count: Mapped[int] = mapped_column(Integer, default=0)
    status_notify_interval_seconds: Mapped[int] = mapped_column(Integer, default=14400)
    max_daily_loss_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.02"))
    max_total_exposure_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.30"))
    max_per_market_exposure_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.10"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class TimeframeConfig(Base):
    """Enabled/disabled timeframe rows."""

    __tablename__ = "timeframe_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Candle(Base):
    """OHLCV candles by market/timeframe."""

    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("market", "timeframe", "candle_time_utc", name="uq_candle_market_tf_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    candle_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    high: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    low: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    close: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 8))


class Order(Base):
    """Order intent and exchange status."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    market: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    ord_type: Mapped[str] = mapped_column(String(16))
    requested_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    requested_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    client_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    intent: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    upbit_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    upbit_uuid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(16), default="NEW", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_class: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exchange_response_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    attempts: Mapped[list["OrderAttempt"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    fills: Mapped[list[Fill]] = relationship(back_populates="order")
    trade_metrics: Mapped[list[TradeMetric]] = relationship(back_populates="order")


class OrderAttempt(Base):
    """Individual exchange submission and recovery attempts for a logical order."""

    __tablename__ = "order_attempts"
    __table_args__ = (
        UniqueConstraint("order_id", "attempt_no", name="uq_order_attempt_order_attempt_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    submit_reason: Mapped[str] = mapped_column(String(16), default="INITIAL")
    requested_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    requested_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    upbit_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    upbit_uuid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(16), default="NEW", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_class: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exchange_response_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    order: Mapped[Order] = relationship(back_populates="attempts")


class Fill(Base):
    """Fill rows for each order (idempotent by trade_id)."""

    __tablename__ = "fills"
    __table_args__ = (UniqueConstraint("trade_id", name="uq_fill_trade_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    trade_id: Mapped[str] = mapped_column(String(64), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    fee: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    is_applied: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    order: Mapped[Order] = relationship(back_populates="fills")


class TradeMetric(Base):
    """Execution quality metrics captured per order."""

    __tablename__ = "trade_metrics"
    __table_args__ = (UniqueConstraint("order_id", name="uq_trade_metrics_order_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    intent: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    intended_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    filled_vwap_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    slippage_abs: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    slippage_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    fee_abs: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    time_to_fill_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    partial_fill_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    order: Mapped[Order] = relationship(back_populates="trade_metrics")


class Position(Base):
    """Current position state per market."""

    __tablename__ = "positions"

    market: Mapped[str] = mapped_column(String(32), primary_key=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    avg_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DailyEquity(Base):
    """Daily equity and pnl snapshot."""

    __tablename__ = "daily_equity"

    date_utc: Mapped[date] = mapped_column(Date, primary_key=True)
    start_equity: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    start_realized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    last_equity: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    daily_pnl_abs: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    daily_pnl_pct: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PaperWallet(Base):
    """Paper cash wallet."""

    __tablename__ = "paper_wallet"

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_krw: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("1000000"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
