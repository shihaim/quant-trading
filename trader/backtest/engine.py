from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.config.config_repo import RuntimeConfig
from trader.data.models import Candle
from trader.trading.risk import RiskEngine
from trader.trading.strategy import EmaCrossStrategy


@dataclass(frozen=True)
class BacktestConfig:
    """백테스트 입력값과 리스크/체결 가정을 담는 설정."""

    market: str
    timeframe: str
    initial_cash_krw: Decimal
    fee_rate: Decimal
    slippage_bps: Decimal
    max_total_exposure_pct: Decimal = Decimal("0.30")
    max_per_market_exposure_pct: Decimal = Decimal("0.10")
    max_daily_loss_pct: Decimal = Decimal("0.02")


@dataclass(frozen=True)
class BacktestResult:
    """백테스트 결과 요약 지표."""

    market: str
    timeframe: str
    trades: int
    start_equity: Decimal
    end_equity: Decimal
    total_return_pct: Decimal
    max_drawdown_pct: Decimal


class BacktestEngine:
    def __init__(self, session: Session):
        """백테스트 엔진을 DB 세션과 함께 초기화한다."""
        self.session = session
        self.strategy = EmaCrossStrategy()
        self.risk = RiskEngine()

    def run(self, cfg: BacktestConfig) -> BacktestResult:
        """캔들을 순차 재생하며 수수료/슬리피지를 반영해 성과를 계산한다."""
        candles = self.session.scalars(
            select(Candle)
            .where(Candle.market == cfg.market, Candle.timeframe == cfg.timeframe)
            .order_by(Candle.candle_time_utc.asc())
        ).all()
        if len(candles) < 100:
            raise ValueError("Not enough candles in DB for backtest. Backfill first.")
        runtime_cfg = RuntimeConfig(
            is_enabled=True,
            timeframe=cfg.timeframe,
            markets=[cfg.market],
            max_daily_loss_pct=cfg.max_daily_loss_pct,
            max_total_exposure_pct=cfg.max_total_exposure_pct,
            max_per_market_exposure_pct=cfg.max_per_market_exposure_pct,
        )
        cash = cfg.initial_cash_krw
        qty = Decimal("0")
        trades = 0
        peak = cfg.initial_cash_krw
        max_drawdown = Decimal("0")

        for idx in range(80, len(candles)):
            window = candles[: idx + 1]
            close_price = Decimal(window[-1].close)
            if close_price <= 0:
                continue
            equity = cash + (qty * close_price)
            signal = self.strategy.evaluate(window, None)
            decision = self.risk.evaluate(signal=signal, config=runtime_cfg, daily_pnl_pct=Decimal("0"))
            target_notional = equity * decision.target_exposure_pct
            target_qty = target_notional / close_price
            delta = target_qty - qty
            if abs(delta) >= Decimal("0.00000001"):
                fill_price = close_price
                if delta > 0:
                    fill_price = close_price * (Decimal("1") + (cfg.slippage_bps / Decimal("10000")))
                    cost = delta * fill_price
                    fee = cost * cfg.fee_rate
                    spend = cost + fee
                    if spend > cash:
                        affordable_qty = cash / (fill_price * (Decimal("1") + cfg.fee_rate))
                        delta = max(Decimal("0"), affordable_qty)
                        cost = delta * fill_price
                        fee = cost * cfg.fee_rate
                        spend = cost + fee
                    cash -= spend
                    qty += delta
                else:
                    sell_qty = min(abs(delta), qty)
                    fill_price = close_price * (Decimal("1") - (cfg.slippage_bps / Decimal("10000")))
                    proceeds = sell_qty * fill_price
                    fee = proceeds * cfg.fee_rate
                    cash += proceeds - fee
                    qty -= sell_qty
                trades += 1
            equity = cash + (qty * close_price)
            if equity > peak:
                peak = equity
            if peak > 0:
                drawdown = (peak - equity) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        end_equity = cash + (qty * Decimal(candles[-1].close))
        total_return = (end_equity - cfg.initial_cash_krw) / cfg.initial_cash_krw if cfg.initial_cash_krw > 0 else Decimal("0")
        return BacktestResult(
            market=cfg.market,
            timeframe=cfg.timeframe,
            trades=trades,
            start_equity=cfg.initial_cash_krw,
            end_equity=end_equity,
            total_return_pct=total_return * Decimal("100"),
            max_drawdown_pct=max_drawdown * Decimal("100"),
        )
