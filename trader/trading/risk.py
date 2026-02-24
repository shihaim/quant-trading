from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trader.config.config_repo import RuntimeConfig
from trader.trading.strategy import StrategySignal


@dataclass(frozen=True)
class RiskDecision:
    """리스크 엔진이 반환하는 거래 허용/중단 결정."""

    halted: bool
    target_exposure_pct: Decimal
    reason: str


class RiskEngine:
    def evaluate(
        self,
        signal: StrategySignal,
        config: RuntimeConfig,
        daily_pnl_pct: Decimal,
    ) -> RiskDecision:
        """신호와 한도를 바탕으로 최종 목표 노출 비중을 확정한다."""
        if not config.is_enabled:
            return RiskDecision(halted=True, target_exposure_pct=Decimal("0"), reason="bot_disabled")
        if daily_pnl_pct <= -abs(config.max_daily_loss_pct):
            return RiskDecision(halted=True, target_exposure_pct=Decimal("0"), reason="daily_loss_limit")
        capped = min(signal.target_exposure_pct, config.max_per_market_exposure_pct, config.max_total_exposure_pct)
        if signal.action == "SELL":
            capped = Decimal("0")
        return RiskDecision(halted=False, target_exposure_pct=capped, reason="ok")
