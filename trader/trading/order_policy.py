from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrderIntent(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    REBALANCE = "REBALANCE"


@dataclass(frozen=True)
class PolicyDecision:
    intent: OrderIntent
    order_type: str
    fill_timeout_sec: int
    max_reprice_attempts: int
    reprice_step_bps: int
    allow_market_fallback: bool


@dataclass(frozen=True)
class OrderPolicyConfig:
    fill_timeout_sec_entry: int = 10
    fill_timeout_sec_exit: int = 4
    fill_timeout_sec_rebalance: int = 10
    max_reprice_attempts_entry: int = 2
    max_reprice_attempts_exit: int = 1
    max_reprice_attempts_rebalance: int = 1
    reprice_step_bps: int = 10
    allow_market_fallback_on_exit: bool = False


class OrderPolicy:
    """Deterministic order policy resolver by intent."""

    def decide(
        self,
        intent: OrderIntent,
        cfg: OrderPolicyConfig,
        is_stop: bool = False,
        is_hard_halt: bool = False,
    ) -> PolicyDecision:
        if intent == OrderIntent.ENTRY:
            return PolicyDecision(
                intent=intent,
                order_type="LIMIT",
                fill_timeout_sec=max(0, int(cfg.fill_timeout_sec_entry)),
                max_reprice_attempts=max(1, int(cfg.max_reprice_attempts_entry)),
                reprice_step_bps=max(1, int(cfg.reprice_step_bps)),
                allow_market_fallback=False,
            )
        if intent == OrderIntent.EXIT:
            aggressive = is_stop or is_hard_halt
            return PolicyDecision(
                intent=intent,
                order_type="AGGRESSIVE_LIMIT" if aggressive else "LIMIT",
                fill_timeout_sec=max(0, int(cfg.fill_timeout_sec_exit)),
                max_reprice_attempts=max(1, int(cfg.max_reprice_attempts_exit)),
                reprice_step_bps=max(1, int(cfg.reprice_step_bps)),
                allow_market_fallback=bool(cfg.allow_market_fallback_on_exit),
            )
        return PolicyDecision(
            intent=OrderIntent.REBALANCE,
            order_type="LIMIT",
            fill_timeout_sec=max(0, int(cfg.fill_timeout_sec_rebalance)),
            max_reprice_attempts=max(1, int(cfg.max_reprice_attempts_rebalance)),
            reprice_step_bps=max(1, int(cfg.reprice_step_bps)),
            allow_market_fallback=False,
        )


def resolve_intent(current_exposure, target_exposure) -> OrderIntent:
    if target_exposure > current_exposure:
        return OrderIntent.ENTRY
    if target_exposure < current_exposure:
        return OrderIntent.EXIT
    return OrderIntent.REBALANCE
