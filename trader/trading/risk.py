from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trader.config.config_repo import RuntimeConfig
from trader.trading.strategy import StrategySignal


@dataclass(frozen=True)
class RiskDecision:
    """Risk decision result for the current loop."""

    halted: bool
    target_exposure_pct: Decimal
    reason: str


def should_skip_rebalance(
    current_exposure_pct: Decimal,
    target_exposure_pct: Decimal,
    min_rebalance_threshold_pct: Decimal,
) -> bool:
    threshold = abs(Decimal(str(min_rebalance_threshold_pct)))
    if threshold <= 0:
        return False
    delta = abs(Decimal(str(target_exposure_pct)) - Decimal(str(current_exposure_pct)))
    return delta < threshold


class RiskEngine:
    def evaluate(
        self,
        signal: StrategySignal,
        config: RuntimeConfig,
        daily_pnl_pct: Decimal,
    ) -> RiskDecision:
        """Return final allowed target exposure after risk guards."""
        if not config.is_enabled:
            return RiskDecision(halted=True, target_exposure_pct=Decimal("0"), reason="bot_disabled")
        if daily_pnl_pct <= -abs(config.max_daily_loss_pct):
            return RiskDecision(halted=True, target_exposure_pct=Decimal("0"), reason="daily_loss_limit")
        capped = min(signal.target_exposure_pct, config.max_per_market_exposure_pct, config.max_total_exposure_pct)
        if signal.action == "SELL":
            capped = Decimal("0")
        return RiskDecision(halted=False, target_exposure_pct=capped, reason="ok")
