from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trader.data.models import Candle, Position


@dataclass(frozen=True)
class StrategySignal:
    """전략이 산출한 행동과 목표 익스포저 비중."""

    action: str
    target_exposure_pct: Decimal
    reason: str


class Strategy:
    def evaluate(self, candles: list[Candle], position: Position | None) -> StrategySignal:
        """캔들과 현재 포지션을 받아 전략 신호를 계산한다."""
        raise NotImplementedError


class EmaCrossStrategy(Strategy):
    def __init__(self, fast: int = 20, slow: int = 60, buy_target_exposure_pct: Decimal = Decimal("0.10")):
        """EMA 단기/장기 기간과 기본 매수 비중을 초기화한다."""
        if fast >= slow:
            raise ValueError("fast must be less than slow")
        self.fast = fast
        self.slow = slow
        self.set_buy_target_exposure_pct(buy_target_exposure_pct)

    def set_buy_target_exposure_pct(self, value: Decimal) -> None:
        """BUY 신호 시 사용할 목표 비중을 동적으로 갱신한다."""
        pct = Decimal(str(value))
        if pct <= 0:
            pct = Decimal("0.10")
        if pct > Decimal("1"):
            pct = Decimal("1")
        self.buy_target_exposure_pct = pct

    def evaluate(self, candles: list[Candle], position: Position | None) -> StrategySignal:
        """EMA 교차로 매수/매도/대기 신호를 만든다."""
        if len(candles) < self.slow + 5:
            return StrategySignal(action="HOLD", target_exposure_pct=Decimal("0"), reason="insufficient_data")
        closes = [Decimal(c.close) for c in candles]
        fast_ema = self._ema(closes, self.fast)
        slow_ema = self._ema(closes, self.slow)
        if fast_ema > slow_ema:
            return StrategySignal(action="BUY", target_exposure_pct=self.buy_target_exposure_pct, reason="ema_bullish")
        return StrategySignal(action="SELL", target_exposure_pct=Decimal("0.00"), reason="ema_bearish")

    @staticmethod
    def _ema(values: list[Decimal], period: int) -> Decimal:
        """주어진 가격 시퀀스의 EMA 최종값을 계산한다."""
        k = Decimal("2") / Decimal(period + 1)
        ema = values[0]
        for price in values[1:]:
            ema = (price * k) + (ema * (Decimal("1") - k))
        return ema
