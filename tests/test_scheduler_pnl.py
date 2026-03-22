from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from trader.config.config_repo import RuntimeConfig
from trader.trading.risk import RiskDecision
from trader.trading.scheduler import TradingScheduler
from trader.trading.strategy import StrategySignal


@dataclass
class _Wallet:
    cash_krw: Decimal


@dataclass
class _Snapshot:
    cash_krw: Decimal
    market_value: Decimal
    total_equity: Decimal


@dataclass
class _DailySnapshot:
    date_utc: object
    start_equity: Decimal
    start_realized_pnl: Decimal
    last_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    daily_pnl_abs: Decimal
    daily_pnl_pct: Decimal


@dataclass
class _Candle:
    close: Decimal
    candle_time_utc: datetime


class _CandleServiceStub:
    def ensure_backfill(self, market: str, timeframe: str, count: int) -> None:
        return None

    def upsert_latest_complete(self, market: str, timeframe: str) -> None:
        return None

    def recent_candles(self, market: str, timeframe: str, count: int) -> list[_Candle]:
        return [_Candle(close=Decimal("90000000"), candle_time_utc=datetime(2026, 2, 24, 5, 45, tzinfo=timezone.utc))]


class _StrategyStub:
    def set_buy_target_exposure_pct(self, value: Decimal) -> None:
        self.buy_target_exposure_pct = value

    def evaluate(self, candles: list[_Candle], position) -> StrategySignal:
        return StrategySignal(action="BUY", target_exposure_pct=Decimal("0.10"), reason="stub_buy")


class _RiskStub:
    def __init__(self):
        self.last_daily_pnl_pct: Decimal | None = None

    def evaluate(self, signal: StrategySignal, config: RuntimeConfig, daily_pnl_pct: Decimal, **kwargs) -> RiskDecision:
        self.last_daily_pnl_pct = daily_pnl_pct
        return RiskDecision(halted=True, target_exposure_pct=Decimal("0"), reason="daily_loss_limit")


class _PortfolioStub:
    def get_or_create_paper_wallet(self, initial_cash_krw: Decimal, *, user_id: int = 1) -> _Wallet:
        return _Wallet(cash_krw=Decimal("10000"))

    def snapshot(self, mark_prices: dict[str, Decimal], cash_krw: Decimal, *, user_id: int = 1) -> _Snapshot:
        return _Snapshot(cash_krw=cash_krw, market_value=Decimal("0"), total_equity=cash_krw)

    def update_unrealized_pnl(self, mark_prices: dict[str, Decimal], *, user_id: int = 1) -> Decimal:
        return Decimal("0")

    def total_unrealized_pnl(self, markets: list[str] | None = None, *, user_id: int = 1) -> Decimal:
        return Decimal("0")

    def total_realized_pnl(self, markets: list[str] | None = None, *, user_id: int = 1) -> Decimal:
        return Decimal("0")

    def get_position(self, market: str, *, user_id: int = 1):
        return None


class _PnlStub:
    def update_daily_snapshot(
        self,
        current_equity: Decimal,
        realized_pnl: Decimal,
        unrealized_pnl: Decimal,
        user_id: int = 1,
        as_of_date_utc=None,
    ) -> _DailySnapshot:
        return _DailySnapshot(
            date_utc=datetime(2026, 2, 24, tzinfo=timezone.utc).date(),
            start_equity=Decimal("10000"),
            start_realized_pnl=Decimal("0"),
            last_equity=current_equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            daily_pnl_abs=Decimal("-300"),
            daily_pnl_pct=Decimal("-0.03"),
        )

    def resolve_daily_pnl_pct(self, snapshot: _DailySnapshot, basis: str, current_realized_pnl: Decimal):
        return snapshot.daily_pnl_abs, snapshot.daily_pnl_pct


class _ExecutionStub:
    def place_target_order(self, **kwargs):
        raise AssertionError("halted 상태에서는 주문 생성이 호출되면 안 된다")


class _NotifierStub:
    def __init__(self):
        self.messages: list[str] = []

    def send(self, text: str) -> None:
        self.messages.append(text)


def _cfg(daily_loss_basis: str = "TOTAL") -> RuntimeConfig:
    return RuntimeConfig(
        is_enabled=True,
        timeframe="1m",
        markets=["KRW-BTC"],
        max_daily_loss_pct=Decimal("0.02"),
        max_total_exposure_pct=Decimal("0.30"),
        max_per_market_exposure_pct=Decimal("0.10"),
        target_exposure_pct=Decimal("0.10"),
        daily_loss_basis=daily_loss_basis,
    )


def test_scheduler_uses_computed_daily_pnl_pct_for_risk():
    scheduler = TradingScheduler.__new__(TradingScheduler)
    scheduler.trade_mode = "PAPER"
    scheduler.is_paper = True
    scheduler.user_id = 1
    scheduler.allowed_markets = set()
    scheduler.candle_service = _CandleServiceStub()
    scheduler.strategy = _StrategyStub()
    scheduler.risk = _RiskStub()
    scheduler.portfolio = _PortfolioStub()
    scheduler.execution = _ExecutionStub()
    scheduler.reconcile = None
    scheduler.pnl = _PnlStub()
    scheduler.notifier = _NotifierStub()

    scheduler._run_once(_cfg())

    assert scheduler.risk.last_daily_pnl_pct == Decimal("-0.03")
    assert any("HALT KRW-BTC" in msg for msg in scheduler.notifier.messages)


def test_scheduler_uses_basis_from_runtime_config():
    scheduler = TradingScheduler.__new__(TradingScheduler)
    scheduler.trade_mode = "PAPER"
    scheduler.is_paper = True
    scheduler.user_id = 1
    scheduler.allowed_markets = set()
    scheduler.candle_service = _CandleServiceStub()
    scheduler.strategy = _StrategyStub()
    scheduler.risk = _RiskStub()
    scheduler.portfolio = _PortfolioStub()
    scheduler.execution = _ExecutionStub()
    scheduler.reconcile = None
    scheduler.pnl = _PnlStub()
    scheduler.notifier = _NotifierStub()

    scheduler._run_once(_cfg(daily_loss_basis="REALIZED_ONLY"))

    assert scheduler.risk.last_daily_pnl_pct == Decimal("-0.03")
