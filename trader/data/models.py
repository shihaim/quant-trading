from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from trader.data.db import Base


def utc_now() -> datetime:
    """UTC 현재 시각을 반환한다."""
    return datetime.now(timezone.utc)


class BotConfig(Base):
    """봇 런타임 설정(ON/OFF, 타임프레임, 리스크 한도)."""

    __tablename__ = "bot_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    timeframe: Mapped[str] = mapped_column(String(16), default="15m")
    markets_json: Mapped[str] = mapped_column(Text, default='["KRW-BTC"]')
    target_exposure_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.10"))
    max_daily_loss_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.02"))
    max_total_exposure_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.30"))
    max_per_market_exposure_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.10"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class TimeframeConfig(Base):
    """실행 가능한 타임프레임 목록과 활성 여부."""

    __tablename__ = "timeframe_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Candle(Base):
    """마켓/타임프레임별 OHLCV 봉 데이터."""

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
    """주문 요청/상태 추적을 위한 주문 원장."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    market: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    ord_type: Mapped[str] = mapped_column(String(16))
    requested_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    requested_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    client_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    upbit_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    upbit_uuid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(16), default="NEW", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_class: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exchange_response_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    fills: Mapped[list[Fill]] = relationship(back_populates="order")


class Fill(Base):
    """주문별 체결 내역(중복 방지 trade_id 포함)."""

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


class Position(Base):
    """현재 보유 수량/평단/손익 상태."""

    __tablename__ = "positions"

    market: Mapped[str] = mapped_column(String(32), primary_key=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    avg_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class PaperWallet(Base):
    """페이퍼 모드 현금 지갑."""

    __tablename__ = "paper_wallet"

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_krw: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("1000000"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
